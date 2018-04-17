from __future__ import absolute_import
from __future__ import print_function
import datetime
import os
import pickle
import sys
import traceback
from fabric.operations import sudo
from fabric.context_managers import settings
from fabric.api import local
import re
from getpass import getpass

from github import Github, UnknownObjectException, GithubException
from fabric.api import execute, env
from fabric.colors import magenta

from .const import (
    PROJECT_ROOT,
    CACHED_DEPLOY_CHECKPOINT_FILENAME,
    CACHED_DEPLOY_ENV_FILENAME,
    DATE_FMT,
    OFFLINE_STAGING_DIR,
)

from six.moves import input


global_github = None


def execute_with_timing(fn, *args, **kwargs):
    start_time = datetime.datetime.utcnow()
    execute(fn, *args, **kwargs)
    if env.timing_log:
        with open(env.timing_log, 'a') as timing_log:
            duration = datetime.datetime.utcnow() - start_time
            timing_log.write('{}: {}\n'.format(fn.__name__, duration.seconds))


def get_pillow_env_config():
    full_host = env.get('host_string')
    if full_host and '.' in full_host:
        host = full_host.split('.')[0]

    pillows = {}
    pillows.update(env.pillows.get(host, {}))
    pillows.update(env.pillows.get(full_host, {}))
    return pillows


class DeployMetadata(object):
    def __init__(self, code_branch, environment):
        self.timestamp = datetime.datetime.utcnow().strftime(DATE_FMT)
        self._deploy_ref = None
        self._deploy_tag = None
        self._max_tags = 100
        self._last_tag = None
        self._code_branch = code_branch
        self._environment = environment

    def tag_commit(self):
        if env.offline:
            self._offline_tag_commit()
            return

        pattern = ".*-{}-deploy".format(re.escape(self._environment))
        github = _get_github()
        repo = github.get_organization('dimagi').get_repo('commcare-hq')
        for tag in repo.get_tags()[:self._max_tags]:
            if re.match(pattern, tag.name):
                self._last_tag = tag.name
                break

        if not self._last_tag:
            print(magenta('Warning: No previous tag found in last {} tags for {}'.format(
                self._max_tags,
                self._environment
            )))
        tag_name = "{}-{}-deploy".format(self.timestamp, self._environment)
        repo.create_git_ref(
            ref='refs/tags/' + tag_name,
            sha=self.deploy_ref,
        )
        self._deploy_tag = tag_name

    def _offline_tag_commit(self):
        commit = local('cd {}/commcare-hq && git show-ref --hash --heads {}'.format(
            OFFLINE_STAGING_DIR,
            env.deploy_metadata.deploy_ref,
        ), capture=True)

        tag_name = '{}-{}-offline-deploy'.format(self.timestamp, self._environment)
        local('cd {staging_dir}/commcare-hq && git tag -a -m "{message}" {tag} {commit}'.format(
            staging_dir=OFFLINE_STAGING_DIR,
            message='{} offline deploy at {}'.format(self._environment, self.timestamp),
            tag=tag_name,
            commit=commit,
        ))

        with settings(warn_only=True):
            local('cd {staging_dir}/commcare-hq && git push origin {tag}'.format(
                staging_dir=OFFLINE_STAGING_DIR,
                tag=tag_name,
            ))

    @property
    def diff_url(self):
        if env.offline:
            return '"No diff url for offline deploy"'

        if self._deploy_tag is None:
            raise Exception("You haven't tagged anything yet.")
        if not self._last_tag:
            return '"Previous deploy not found, cannot make comparison"'
        return "https://github.com/dimagi/commcare-hq/compare/{}...{}".format(
            self._last_tag,
            self._deploy_tag,
        )

    @property
    def deploy_ref(self):
        if self._deploy_ref is not None:
            return self._deploy_ref

        # https://github.com/PyGithub/PyGithub/pull/709
        uses_proxy = os.getenv('http_proxy') or os.getenv('HTTP_PROXY')
        if env.offline or uses_proxy:
            self._deploy_ref = env.code_branch
            return self._deploy_ref

        github = _get_github()
        repo = github.get_organization('dimagi').get_repo('commcare-hq')

        # turn whatever `code_branch` is into a commit hash
        branch = repo.get_branch(self._code_branch)
        self._deploy_ref = branch.commit.sha

        try:
            repo.create_git_ref(
                ref='refs/tags/' + '{}-{}-setup_release'.format(self.timestamp, self._environment),
                sha=self._deploy_ref,
            )
        except UnknownObjectException:
            raise Exception(
                'Github API key does not have the right settings. '
                'Please create an API key with the public_repo scope enabled.'
            )
        except GithubException as e:
            if e.data.get('message') != 'Reference already exists':
                raise

        return self._deploy_ref


def _get_github():
    """
    This grabs the dimagi github account and stores the state in a global variable.
    We do not store it in `env` or `DeployMetadata` so that it's possible to
    unpickle the `env` object without hitting the recursion limit.
    """
    global global_github

    if global_github is not None:
        return global_github
    try:
        from .config import GITHUB_APIKEY
    except ImportError:
        print((
            "You can add a GitHub API key to automate this step:\n"
            "    $ cp {project_root}/config.example.py {project_root}/config.py\n"
            "Then edit {project_root}/config.py"
        ).format(project_root=PROJECT_ROOT))
        username = input('Github username: ')
        password = getpass('Github password: ')
        global_github = Github(
            login_or_token=username,
            password=password,
        )
    else:
        global_github = Github(
            login_or_token=GITHUB_APIKEY,
        )

    return global_github


def _get_checkpoint_filename():
    return '{}_{}'.format(env.deploy_env, CACHED_DEPLOY_CHECKPOINT_FILENAME)


def _get_env_filename():
    return '{}_{}'.format(env.deploy_env, CACHED_DEPLOY_ENV_FILENAME)


def cache_deploy_state(command_index):
    with open(os.path.join(PROJECT_ROOT, _get_checkpoint_filename()), 'w') as f:
        pickle.dump(command_index, f)
    with open(os.path.join(PROJECT_ROOT, _get_env_filename()), 'w') as f:
        pickle.dump(env, f)


def clear_cached_deploy():
    os.remove(os.path.join(PROJECT_ROOT, _get_checkpoint_filename()))
    os.remove(os.path.join(PROJECT_ROOT, _get_env_filename()))


def retrieve_cached_deploy_env():
    filename = os.path.join(PROJECT_ROOT, _get_env_filename())
    return _retrieve_cached(filename)


def retrieve_cached_deploy_checkpoint():
    filename = os.path.join(PROJECT_ROOT, _get_checkpoint_filename())
    return _retrieve_cached(filename)


def _retrieve_cached(filename):
    with open(filename, 'r') as f:
        return pickle.load(f)


def traceback_string():
    exc_type, exc, tb = sys.exc_info()
    trace = "".join(traceback.format_tb(tb))
    return u"Traceback:\n{trace}{type}: {exc}".format(
        trace=trace,
        type=exc_type.__name__,
        exc=exc,
    )


def pip_install(cmd_prefix, requirements, timeout=None, quiet=False, proxy=None, no_index=False,
        wheel_dir=None):
    parts = [cmd_prefix, 'pip install']
    if timeout is not None:
        parts.append('--timeout {}'.format(timeout))
    if quiet:
        parts.append('--quiet')
    for requirement in requirements:
        parts.append('--requirement {}'.format(requirement))
    if proxy is not None:
        parts.append('--proxy {}'.format(proxy))
    if no_index:
        parts.append('--no-index')
    if wheel_dir is not None:
        parts.append('--find-links={}'.format(wheel_dir))
    sudo(' '.join(parts))


def generate_bower_command(command, production=True, config=None):
    parts = ['bower', command]
    if production:
        parts.append('--production')
    if config:
        for key, value in config.items():
            parts.append('--config.{}={}'.format(key, value))
    return ' '.join(parts)


def bower_command(command, production=True, config=None):
    cmd = generate_bower_command(command, production, config)
    sudo(cmd)
