# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
import dateutil.relativedelta

_logger = logging.getLogger(__name__)


class DataModelActivity(models.Model):
    _name = 'tender_cat.data.model.activity'
    _description = "Data model activity"

    name = fields.Char(string='Name')

    data_model_id = fields.Many2one('tender_cat.data.model', string='Data model', index=True)
    activity_type = fields.Char(string='Type')
    activity_log = fields.Text(string='Log')
    user_id = fields.Many2one('res.users', string='User', index=True)
    start_time = fields.Datetime(string='Start', default=lambda self: fields.Datetime.now())
    end_time = fields.Datetime(string='End')
    duration = fields.Char(string='Duration')

    _order = 'start_time desc'

    @api.model
    def default_get(self, default_fields):
        result = super(DataModelActivity, self).default_get(default_fields)
        active_model = self._context.get('active_model')
        if active_model == 'tender_cat.data.model':
            active_id = self._context.get('active_id')
            if active_id:
                result['data_model_id'] = self.env['tender_cat.data.model'].browse(active_id).id

        result['user_id'] = self.env.user.id

        return result

    def run(self, data_model_id):
        data_model = self.env['tender_cat.data.model'].browse(data_model_id).id
        data_model.refit_model()

        now = fields.Datetime.now()
        if self.start_time:
            rd = dateutil.relativedelta.relativedelta(now, self.start_time)
            duration = str('{}h {}min {}sec').format(rd.hours, rd.minutes, rd.seconds)

        self.write({
            'end_time': now,
            'duration': duration,
        })



