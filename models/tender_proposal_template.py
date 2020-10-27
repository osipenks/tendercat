# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging


_logger = logging.getLogger(__name__)


class TenderProposalTemplate(models.Model):
    _name = 'tender_cat.tender.proposal.template'
    _description = "Tender proposal template"

    name = fields.Char(string='Name')
    description = fields.Text(string='Detailed description')

    line_ids = fields.One2many(
        'tender_cat.tender.proposal.template.line', 'proposal_template_id', string='Documents',
        copy=True)


class TenderProposalTemplateLine(models.Model):
    _name = 'tender_cat.tender.proposal.template.line'
    _description = "Tender proposal template's line"

    sequence = fields.Integer('Sequence', default=1, help="Gives the sequence order when displaying.")

    line_number = fields.Integer(compute='_compute_get_number', store=True, )

    proposal_template_id = fields.Many2one('tender_cat.tender.proposal.template', 'Proposal template',
                                           index=True, ondelete='cascade', required=True)

    # label_id = fields.Many2one('tender_cat.label', string='Label', copy=True)

    label_ids = fields.Many2many('tender_cat.label', string='Label', index=True)

    document_id = fields.Many2one('tender_cat.tender.document', string='Document', required=True)

    @api.depends('sequence', 'proposal_template_id')
    def _compute_get_number(self):
        for template in self.mapped('proposal_template_id'):
            _logger.info('template {}'.format(template))
            number = 1
            template_lines = self.env['tender_cat.tender.proposal.template'].browse(template.id).line_ids.sorted('sequence')
            for line in template_lines:
                _logger.info('line {}'.format(line))
                line.line_number = number
                number += 1
