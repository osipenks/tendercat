# -*- coding: utf-8 -*-

from odoo import fields
import psycopg2
import threading
import time
from odoo import registry as registry_get
from odoo.sql_db import db_connect
import logging
import pandas as pd
import os

_logger = logging.getLogger(__name__)


def folder_csv_to_dataframe(folder):
    csvs = []
    for root, dirs, files in os.walk(folder):
        for f in files:
            if f.endswith(".csv"):
                try:
                    csvs.append(pd.read_csv(os.path.join(folder, f)))
                except (FileExistsError, IOError, pd.errors.EmptyDataError) as e:
                    _logger.error('{}: {}'.format(f, e))
    if csvs:
        return pd.concat(csvs, ignore_index=True)
    else:
        return pd.DataFrame()


def start_cron_task(obj, task_name, code):

    cron_vals = {
        'numbercall': 1,
        'active': 1,
        'state': 'code',
        'priority': 5000,
        'usage': 'ir_cron',
        'nextcall': fields.Datetime.now(),
        'code': code,
    }
    cron_id = 0
    cr = obj._cr
    cr.execute("""SELECT id FROM ir_cron WHERE cron_name = %s LIMIT 1""", (task_name,))
    try:
        cron_id = cr.dictfetchone()['id']
    except:
        pass

    cron = obj.env['ir.cron'].browse(cron_id)
    if cron.id:
        cron.write(cron_vals)
        cron_record = cron
    else:
        cron_vals.update({
            'name': task_name,
            'model_id': obj.env.ref('tender_cat.model_tender_cat_data_model_activity').id,
            'user_id': obj.env.uid,
            'interval_type': 'minutes',
        })
        cron_record = cron.create(cron_vals)

    obj._cr.commit()
    _run_cron_job(obj._cr.dbname, cron_record.id)


def _run_cron_job(db_name, job_id):

    def target():
        _run_cron_thread(db_name, job_id)

    t = threading.Thread(target=target, name="odoo.service.cron.cron%d" % job_id)
    t.setDaemon(True)
    t.type = 'cron'
    t.start()


def _run_cron_thread(db_name, job_id):
    registry = registry_get(db_name)
    db = db_connect(db_name)
    threading.current_thread().dbname = db_name
    if registry.ready:
        thread = threading.currentThread()
        thread.start_time = time.time()
        try:

            with db.cursor() as cr:
                # Careful to compare timestamps with 'UTC' - everything is UTC as of v6.1.
                cr.execute("""SELECT * FROM ir_cron
                                         WHERE numbercall != 0
                                             AND active 
                                             AND id=%s
                                         ORDER BY priority""", (job_id,))
                # AND                nextcall <= (now() at time zone 'UTC')
                jobs = cr.dictfetchall()

            for job in jobs:
                lock_cr = db.cursor()
                try:
                    # Try to grab an exclusive lock on the job row from within the task transaction
                    # Restrict to the same conditions as for the search since the job may have already
                    # been run by an other thread when cron is running in multi thread
                    lock_cr.execute("""SELECT *
                                                       FROM ir_cron
                                                       WHERE numbercall != 0
                                                          AND active
                                                          AND id=%s
                                                       FOR UPDATE NOWAIT""",
                                    (job['id'],), log_exceptions=False)

                    locked_job = lock_cr.fetchone()
                    if not locked_job:
                        _logger.info("Job `%s` already executed by another process/thread. skipping it",
                                     job['cron_name'])
                        lock_cr.close()

                    # Got the lock on the job row, run its code
                    _logger.info('Starting job `%s`.', job['cron_name'])

                    job_cr = db.cursor()
                    try:
                        registry['ir.cron']._process_job(job_cr, job, lock_cr)
                        _logger.info('Job `%s` done.', job['cron_name'])
                    except Exception as e:
                        _logger.exception('Unexpected exception while processing cron job {}:\n{}'
                                          .format(job['cron_name'], e))
                    finally:
                        job_cr.close()

                except psycopg2.OperationalError as e:
                    if e.pgcode == '55P03':
                        # Class 55: Object not in prerequisite state; 55P03: lock_not_available
                        _logger.info('Another process/thread is already busy executing job `%s`, skipping it.',
                                     job['cron_name'])
                        continue
                    else:
                        # Unexpected OperationalError
                        raise
                finally:
                    # we're exiting due to an exception while acquiring the lock
                    lock_cr.close()
        finally:
            if hasattr(threading.current_thread(), 'dbname'):
                del threading.current_thread().dbname

        thread.start_time = None
