# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
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

    label_ids = fields.Many2many('tender_cat.label', string='Label', index=True)

    doc_class = fields.Selection([
        ('doc_copy', _('Copy of document')),
        ('doc_report', _('Report')),
        ('doc_template', _('Custom template')),
        ('doc_external', _('External document')),
    ], string='Document class', default='doc_copy')

    doc_repr = fields.Char(string='Document')
    doc_desc = fields.Char(string='Description')

    doc_copy_id = fields.Many2one('tender_cat.tender.document', string='Document')
    doc_report_id = fields.Many2one('tender_cat.tender.doc.report', string='Document')
    doc_template_id = fields.Many2one('tender_cat.tender.doc.template', string='Document')
    doc_external_id = fields.Many2one('tender_cat.tender.doc.external', string='Document')

    @api.depends('sequence', 'proposal_template_id')
    def _compute_get_number(self):
        for template in self.mapped('proposal_template_id'):
            number = 1
            lines = self.env['tender_cat.tender.proposal.template'].browse(template.id).line_ids.sorted('sequence')
            for line in lines:
                line.line_number = number
                number += 1

    @api.onchange('doc_class', 'doc_copy_id', 'doc_report_id', 'doc_template_id', 'doc_external_id')
    def _set_desc(self):
        doc_dct = {
            'doc_copy': self.doc_copy_id,
            'doc_report': self.doc_report_id,
            'doc_template': self.doc_template_id,
            'doc_external': self.doc_external_id,
        }
        active_doc_id = doc_dct.get(self.doc_class)
        if active_doc_id:
            self.doc_desc = active_doc_id.get_desc()
            self.doc_repr = active_doc_id.name
        else:
            self.doc_desc, self.doc_repr = '', ''
