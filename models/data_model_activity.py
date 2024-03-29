# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import logging
import datetime
import dateutil.relativedelta
from . import utils

_logger = logging.getLogger(__name__)


class DataModelActivity(models.Model):
    _name = 'tender_cat.data.model.activity'
    _description = "Data model activity"

    name = fields.Char(string='Name')

    data_model_id = fields.Many2one('tender_cat.data.model', string='Data model', index=True)
    obj_id = fields.Integer(default=0)

    activity_type = fields.Char(string='Type', readonly=True)
    activity_log = fields.Text(string='Log')
    user_id = fields.Many2one('res.users', string='User', index=True)

    start_time = fields.Datetime(string='Start', default=lambda self: fields.Datetime.now(), readonly=True)
    end_time = fields.Datetime(string='End', readonly=True)
    duration = fields.Char(string='Duration', readonly=True)

    is_async = fields.Boolean(default=False)

    _order = 'start_time desc'
    _log_access = False
    _rec_name = 'activity_type'

    @api.model
    def default_get(self, default_fields):
        result = super(DataModelActivity, self).default_get(default_fields)
        active_model = self._context.get('active_model')
        if active_model == 'tender_cat.data.model':
            active_id = self._context.get('active_id')
            if active_id:
                result['data_model_id'] = self.env['tender_cat.data.model'].browse(active_id).id

        result['user_id'] = self.env.user.id
        result['name'] = self.activity_type

        return result

    def write_end_time(self):
        duration = 0
        now = fields.Datetime.now()
        if self.start_time:
            rd = dateutil.relativedelta.relativedelta(now, self.start_time)
            duration = str('{}h {}min {}sec').format(rd.hours, rd.minutes, rd.seconds)

        # This is the end, my only friend...
        log = str(self.activity_log)
        end_msg = log + '\n' + datetime.date.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)+' '+str('End')

        self.write({
            'end_time': now,
            'duration': duration,
            'activity_log': end_msg,
        })

    def run(self):
        msg = 'Run data model\'s {} activity \'{}\''.format(self.data_model_id, self.activity_type)
        if self.activity_type == 'Refit':
            _logger.info(msg)
            data_model = self.env['tender_cat.data.model'].browse(self.data_model_id).id
            activity_obj = self
            data_model.refit_model(a=activity_obj)
        elif self.activity_type == 'Transform':
            _logger.info(msg.join(' on object id:{}').format(self.obj_id))
            data_model = self.env['tender_cat.data.model'].browse(self.data_model_id).id
            data_model.transform_data(obj_id=self.obj_id)

        self.write_end_time()

    def log(self, msg):
        format_msg = datetime.date.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)+' '+str(msg)
        self.write({'activity_log': str(self.activity_log)+'\n'+format_msg, })
        _logger.info(msg)

    warning, info, error = log, log, log


class RunActivity:
    id = 0

    def __init__(self, obj, activity_type, reference_id=None):
        self._env = obj.env
        self._data_model_id = obj.id
        self._activity_type = activity_type
        self._reference_id = reference_id

    def __enter__(self):
        activity = self._env['tender_cat.data.model.activity']
        self.activity = activity.create({
                'data_model_id': self._data_model_id,
                'activity_type': self._activity_type,
                'activity_log': datetime.date.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)+' Start'
                })
        self.id = self.activity.id
        return self.activity

    def __exit__(self, type, value, traceback):
        self.activity.write_end_time()


class RunAsyncActivity(RunActivity):

    def __init__(self, obj, activity_type, reference_id=None):
        super(RunAsyncActivity, self).__init__(obj, activity_type, reference_id)

    def __enter__(self):
        activity = self._env['tender_cat.data.model.activity']
        self.activity = activity.create({
            'data_model_id': self._data_model_id,
            'activity_type': self._activity_type,
            'obj_id': self._reference_id,
            'activity_log': datetime.date.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT) + ' Start',
            'is_async': True,
            })
        self.id = self.activity.id

        # todo: move somewhere to outside
        # self.write({'last_activity_id': new_act.id, 'activity_started': True, })

        code = 'env[\'tender_cat.data.model.activity\'].browse({}).run()'.format(self.activity.id, self._data_model_id)
        task_name = 'Data model {}: {}'.format(self.id, self._activity_type)
        utils.start_cron_task(activity, task_name, code)

        return self.activity

    def __exit__(self, type, value, traceback):
        pass
