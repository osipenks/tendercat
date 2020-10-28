# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from . import data_dump
import logging

_logger = logging.getLogger(__name__)


class CreateProposalWizard(models.TransientModel):
    """
    Create proposal for tender
    """
    _name = 'tender_cat.create.proposal.wizard'
    _description = 'Create proposal for tender'

    tender_id = fields.Many2one('tender_cat.tender', string='Tender')
    proposal_template_id = fields.Many2one('tender_cat.tender.proposal.template', string='Proposal template')

    tender_desc = fields.Char(string='Tender description')
    tender_number = fields.Char(string='Tender')

    @api.model
    def default_get(self, default_fields):
        result = super(CreateProposalWizard, self).default_get(default_fields)

        if 'proposal_template_id' in default_fields:
            found_ids = self.env['tender_cat.tender.proposal.template'].search([], limit=1)
            if found_ids:
                result['proposal_template_id'] = found_ids[0].id

        active_id = self.env.context.get('active_id')
        if active_id:
            result['tender_id'] = active_id
            tender = self.env['tender_cat.tender'].browse(active_id)
            result['tender_desc'] = tender.full_name
            result['tender_number'] = tender.tender_id

        return result

    def action_create_proposal(self):

        return {
            'name': _('Create tender proposal'),
            'res_model': 'tender_cat.create.proposal.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('tender_cat.view_tender_cat_create_proposal_wizard_form').id,
            'context': self.env.context,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def create_proposal(self):
        pass

