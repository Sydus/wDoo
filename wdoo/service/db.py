# -*- coding: utf-8 -*-
import base64
import json
import logging
import os
import shutil
import tempfile
import threading
import traceback
from xml.etree import ElementTree as ET
import zipfile

from psycopg2 import sql
from pytz import country_timezones
from functools import wraps
from contextlib import closing
from decorator import decorator

import psycopg2

import wdoo
from wdoo import SUPERUSER_ID
from wdoo.exceptions import AccessDenied
import wdoo.release
import wdoo.sql_db
import wdoo.tools
from wdoo.sql_db import db_connect
from wdoo.release import version_info

_logger = logging.getLogger(__name__)

class DatabaseExists(Warning):
    pass


def check_db_management_enabled(method):
    def if_db_mgt_enabled(method, self, *args, **kwargs):
        if not wdoo.tools.config['list_db']:
            _logger.error('Database management functions blocked, admin disabled database listing')
            raise AccessDenied()
        return method(self, *args, **kwargs)
    return decorator(if_db_mgt_enabled, method)

#----------------------------------------------------------
# Master password required
#----------------------------------------------------------

def check_super(passwd):
    if passwd and wdoo.tools.config.verify_admin_password(passwd):
        return True
    raise wdoo.exceptions.AccessDenied()

# This should be moved to wdoo.modules.db, along side initialize().
def _initialize_db(id, db_name, demo, lang, user_password, login='admin', tz=None, phone=None):
    try:
        db = wdoo.sql_db.db_connect(db_name)
        with closing(db.cursor()) as cr:
            # TODO this should be removed as it is done by Registry.new().
            wdoo.modules.db.initialize(cr)
            wdoo.tools.config['load_language'] = lang
            cr.commit()

        registry = wdoo.modules.registry.Registry.new(db_name, demo, None, update_module=True)

        with closing(registry.cursor()) as cr:
            env = wdoo.api.Environment(cr, SUPERUSER_ID, {})

            if lang:
                modules = env['ir.module.module'].search([('state', '=', 'installed')])
                modules._update_translations(lang)

            if tz:
                users = env['res.users'].search([])
                users.write({'tz': tz})

           
            if '@' in login:
                env['res.company'].browse(1).write({'email': login})

            # update admin's password and lang and login
            values = {'password': user_password, 'lang': lang}
            if login:
                values['login'] = login
                emails = wdoo.tools.email_split(login)
                if emails:
                    values['email'] = emails[0]
            env.ref('base.user_admin').write(values)

            cr.execute('SELECT login, password FROM res_users ORDER BY login')
            cr.commit()
    except Exception as e:
        _logger.exception('CREATE DATABASE failed:')

def _create_empty_database(name):
    db = wdoo.sql_db.db_connect('postgres')
    with closing(db.cursor()) as cr:
        chosen_template = wdoo.tools.config['db_template']
        cr.execute("SELECT datname FROM pg_database WHERE datname = %s",
                   (name,), log_exceptions=False)
        if cr.fetchall():
            raise DatabaseExists("database %r already exists!" % (name,))
        else:
            # database-altering operations cannot be executed inside a transaction
            cr.rollback()
            cr._cnx.autocommit = True

            # 'C' collate is only safe with template0, but provides more useful indexes
            collate = sql.SQL("LC_COLLATE 'C'" if chosen_template == 'template0' else "")
            cr.execute(
                sql.SQL("CREATE DATABASE {} ENCODING 'unicode' {} TEMPLATE {}").format(
                sql.Identifier(name), collate, sql.Identifier(chosen_template)
            ))

    if wdoo.tools.config['unaccent']:
        try:
            db = wdoo.sql_db.db_connect(name)
            with closing(db.cursor()) as cr:
                cr.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
                cr.commit()
        except psycopg2.Error:
            pass

@check_db_management_enabled
def exp_create_database(db_name, demo, lang, user_password='admin', login='admin', tz=None, phone=None):
    """ Similar to exp_create but blocking."""
    _logger.info('Create database `%s`.', db_name)
    _create_empty_database(db_name)
    _initialize_db(id, db_name, demo, lang, user_password, login, tz, phone)
    return True

@check_db_management_enabled
def exp_duplicate_database(db_original_name, db_name):
    _logger.info('Duplicate database `%s` to `%s`.', db_original_name, db_name)
    wdoo.sql_db.close_db(db_original_name)
    db = wdoo.sql_db.db_connect('postgres')
    with closing(db.cursor()) as cr:
        # database-altering operations cannot be executed inside a transaction
        cr._cnx.autocommit = True
        _drop_conn(cr, db_original_name)
        cr.execute(sql.SQL("CREATE DATABASE {} ENCODING 'unicode' TEMPLATE {}").format(
            sql.Identifier(db_name),
            sql.Identifier(db_original_name)
        ))

    registry = wdoo.modules.registry.Registry.new(db_name)
    with registry.cursor() as cr:
        # if it's a copy of a database, force generation of a new dbuuid
        env = wdoo.api.Environment(cr, SUPERUSER_ID, {})
        env['ir.config_parameter'].init(force=True)

    from_fs = wdoo.tools.config.filestore(db_original_name)
    to_fs = wdoo.tools.config.filestore(db_name)
    if os.path.exists(from_fs) and not os.path.exists(to_fs):
        shutil.copytree(from_fs, to_fs)
    return True

def _drop_conn(cr, db_name):
    # Try to terminate all other connections that might prevent
    # dropping the database
    try:
        # PostgreSQL 9.2 renamed pg_stat_activity.procpid to pid:
        # http://www.postgresql.org/docs/9.2/static/release-9-2.html#AEN110389
        pid_col = 'pid' if cr._cnx.server_version >= 90200 else 'procpid'

        cr.execute("""SELECT pg_terminate_backend(%(pid_col)s)
                      FROM pg_stat_activity
                      WHERE datname = %%s AND
                            %(pid_col)s != pg_backend_pid()""" % {'pid_col': pid_col},
                   (db_name,))
    except Exception:
        pass

@check_db_management_enabled
def exp_drop(db_name):
    if db_name not in list_dbs(True):
        return False
    wdoo.modules.registry.Registry.delete(db_name)
    wdoo.sql_db.close_db(db_name)

    db = wdoo.sql_db.db_connect('postgres')
    with closing(db.cursor()) as cr:
        # database-altering operations cannot be executed inside a transaction
        cr._cnx.autocommit = True
        _drop_conn(cr, db_name)

        try:
            cr.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(db_name)))
        except Exception as e:
            _logger.info('DROP DB: %s failed:\n%s', db_name, e)
            raise Exception("Couldn't drop database %s: %s" % (db_name, e))
        else:
            _logger.info('DROP DB: %s', db_name)

    fs = wdoo.tools.config.filestore(db_name)
    if os.path.exists(fs):
        shutil.rmtree(fs)
    return True

@check_db_management_enabled
def exp_dump(db_name, format):
    with tempfile.TemporaryFile(mode='w+b') as t:
        dump_db(db_name, t, format)
        t.seek(0)
        return base64.b64encode(t.read()).decode()

@check_db_management_enabled
def dump_db_manifest(cr):
    pg_version = "%d.%d" % divmod(cr._obj.connection.server_version / 100, 100)
    cr.execute("SELECT name, latest_version FROM ir_module_module WHERE state = 'installed'")
    modules = dict(cr.fetchall())
    manifest = {
        'wdoo_dump': '1',
        'db_name': cr.dbname,
        'version': wdoo.release.version,
        'version_info': wdoo.release.version_info,
        'major_version': wdoo.release.major_version,
        'pg_version': pg_version,
        'modules': modules,
    }
    return manifest

@check_db_management_enabled
def dump_db(db_name, stream, backup_format='zip'):
    """Dump database `db` into file-like object `stream` if stream is None
    return a file object with the dump """

    _logger.info('DUMP DB: %s format %s', db_name, backup_format)

    cmd = ['pg_dump', '--no-owner']
    cmd.append(db_name)

    if backup_format == 'zip':
        with tempfile.TemporaryDirectory() as dump_dir:
            filestore = wdoo.tools.config.filestore(db_name)
            if os.path.exists(filestore):
                shutil.copytree(filestore, os.path.join(dump_dir, 'filestore'))
            with open(os.path.join(dump_dir, 'manifest.json'), 'w') as fh:
                db = wdoo.sql_db.db_connect(db_name)
                with db.cursor() as cr:
                    json.dump(dump_db_manifest(cr), fh, indent=4)
            cmd.insert(-1, '--file=' + os.path.join(dump_dir, 'dump.sql'))
            wdoo.tools.exec_pg_command(*cmd)
            if stream:
                wdoo.tools.osutil.zip_dir(dump_dir, stream, include_dir=False, fnct_sort=lambda file_name: file_name != 'dump.sql')
            else:
                t=tempfile.TemporaryFile()
                wdoo.tools.osutil.zip_dir(dump_dir, t, include_dir=False, fnct_sort=lambda file_name: file_name != 'dump.sql')
                t.seek(0)
                return t
    else:
        cmd.insert(-1, '--format=c')
        stdin, stdout = wdoo.tools.exec_pg_command_pipe(*cmd)
        if stream:
            shutil.copyfileobj(stdout, stream)
        else:
            return stdout

@check_db_management_enabled
def exp_restore(db_name, data, copy=False):
    def chunks(d, n=8192):
        for i in range(0, len(d), n):
            yield d[i:i+n]
    data_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        for chunk in chunks(data):
            data_file.write(base64.b64decode(chunk))
        data_file.close()
        restore_db(db_name, data_file.name, copy=copy)
    finally:
        os.unlink(data_file.name)
    return True

@check_db_management_enabled
def restore_db(db, dump_file, copy=False):
    assert isinstance(db, str)
    if exp_db_exist(db):
        _logger.info('RESTORE DB: %s already exists', db)
        raise Exception("Database already exists")

    _create_empty_database(db)

    filestore_path = None
    with tempfile.TemporaryDirectory() as dump_dir:
        if zipfile.is_zipfile(dump_file):
            # v8 format
            with zipfile.ZipFile(dump_file, 'r') as z:
                # only extract known members!
                filestore = [m for m in z.namelist() if m.startswith('filestore/')]
                z.extractall(dump_dir, ['dump.sql'] + filestore)

                if filestore:
                    filestore_path = os.path.join(dump_dir, 'filestore')

            pg_cmd = 'psql'
            pg_args = ['-q', '-f', os.path.join(dump_dir, 'dump.sql')]

        else:
            # <= 7.0 format (raw pg_dump output)
            pg_cmd = 'pg_restore'
            pg_args = ['--no-owner', dump_file]

        args = []
        args.append('--dbname=' + db)
        pg_args = args + pg_args

        if wdoo.tools.exec_pg_command(pg_cmd, *pg_args):
            raise Exception("Couldn't restore database")

        registry = wdoo.modules.registry.Registry.new(db)
        with registry.cursor() as cr:
            env = wdoo.api.Environment(cr, SUPERUSER_ID, {})
            if copy:
                # if it's a copy of a database, force generation of a new dbuuid
                env['ir.config_parameter'].init(force=True)
            if filestore_path:
                filestore_dest = env['ir.attachment']._filestore()
                shutil.move(filestore_path, filestore_dest)

    _logger.info('RESTORE DB: %s', db)

@check_db_management_enabled
def exp_rename(old_name, new_name):
    wdoo.modules.registry.Registry.delete(old_name)
    wdoo.sql_db.close_db(old_name)

    db = wdoo.sql_db.db_connect('postgres')
    with closing(db.cursor()) as cr:
        # database-altering operations cannot be executed inside a transaction
        cr._cnx.autocommit = True
        _drop_conn(cr, old_name)
        try:
            cr.execute(sql.SQL('ALTER DATABASE {} RENAME TO {}').format(sql.Identifier(old_name), sql.Identifier(new_name)))
            _logger.info('RENAME DB: %s -> %s', old_name, new_name)
        except Exception as e:
            _logger.info('RENAME DB: %s -> %s failed:\n%s', old_name, new_name, e)
            raise Exception("Couldn't rename database %s to %s: %s" % (old_name, new_name, e))

    old_fs = wdoo.tools.config.filestore(old_name)
    new_fs = wdoo.tools.config.filestore(new_name)
    if os.path.exists(old_fs) and not os.path.exists(new_fs):
        shutil.move(old_fs, new_fs)
    return True

@check_db_management_enabled
def exp_change_admin_password(new_password):
    wdoo.tools.config.set_admin_password(new_password)
    wdoo.tools.config.save()
    return True

@check_db_management_enabled
def exp_migrate_databases(databases):
    for db in databases:
        _logger.info('migrate database %s', db)
        wdoo.tools.config['update']['base'] = True
        wdoo.modules.registry.Registry.new(db, force_demo=False, update_module=True)
    return True

#----------------------------------------------------------
# No master password required
#----------------------------------------------------------

@wdoo.tools.mute_logger('wdoo.sql_db')
def exp_db_exist(db_name):
    ## Not True: in fact, check if connection to database is possible. The database may exists
    try:
        db = wdoo.sql_db.db_connect(db_name)
        with db.cursor():
            return True
    except Exception:
        return False

def list_dbs(force=False):
    if not wdoo.tools.config['list_db'] and not force:
        raise wdoo.exceptions.AccessDenied()

    if not wdoo.tools.config['dbfilter'] and wdoo.tools.config['db_name']:
        # In case --db-filter is not provided and --database is passed, wdoo will not
        # fetch the list of databases available on the postgres server and instead will
        # use the value of --database as comma seperated list of exposed databases.
        res = sorted(db.strip() for db in wdoo.tools.config['db_name'].split(','))
        return res

    chosen_template = wdoo.tools.config['db_template']
    templates_list = tuple(set(['postgres', chosen_template]))
    db = wdoo.sql_db.db_connect('postgres')
    with closing(db.cursor()) as cr:
        try:
            cr.execute("select datname from pg_database where datdba=(select usesysid from pg_user where usename=current_user) and not datistemplate and datallowconn and datname not in %s order by datname", (templates_list,))
            res = [wdoo.tools.ustr(name) for (name,) in cr.fetchall()]
        except Exception:
            _logger.exception('Listing databases failed:')
            res = []
    return res

def list_db_incompatible(databases):
    """"Check a list of databases if they are compatible with this version of wdoo
        :param databases: A list of existing Postgresql databases
        :return: A list of databases that are incompatible
    """
    incompatible_databases = []
    server_version = '.'.join(str(v) for v in version_info[:2])
    for database_name in databases:
        with closing(db_connect(database_name).cursor()) as cr:
            if wdoo.tools.table_exists(cr, 'ir_module_module'):
                cr.execute("SELECT latest_version FROM ir_module_module WHERE name=%s", ('base',))
                base_version = cr.fetchone()
                if not base_version or not base_version[0]:
                    incompatible_databases.append(database_name)
                else:
                    # e.g. 10.saas~15
                    local_version = '.'.join(base_version[0].split('.')[:2])
                    if local_version != server_version:
                        incompatible_databases.append(database_name)
            else:
                incompatible_databases.append(database_name)
    for database_name in incompatible_databases:
        # release connection
        wdoo.sql_db.close_db(database_name)
    return incompatible_databases


def exp_list(document=False):
    if not wdoo.tools.config['list_db']:
        raise wdoo.exceptions.AccessDenied()
    return list_dbs()

def exp_list_lang():
    return wdoo.tools.scan_languages()

def exp_server_version():
    """ Return the version of the server
        Used by the client to verify the compatibility with its own version
    """
    return wdoo.release.version

#----------------------------------------------------------
# db service dispatch
#----------------------------------------------------------

def dispatch(method, params):
    g = globals()
    exp_method_name = 'exp_' + method
    if method in ['db_exist', 'list', 'list_lang', 'server_version']:
        return g[exp_method_name](*params)
    elif exp_method_name in g:
        passwd = params[0]
        params = params[1:]
        check_super(passwd)
        return g[exp_method_name](*params)
    else:
        raise KeyError("Method not found: %s" % method)