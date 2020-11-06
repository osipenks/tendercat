# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging
import base64
import tempfile
import os
from .utils import zip_folder


_logger = logging.getLogger(__name__)


class DownloadProposalWizard(models.TransientModel):
    """
    Download tender proposal's files as .zip archive
    """
    _name = 'tender_cat.download.proposal.wizard'
    _description = 'Download proposal files as .zip archive'

    proposal_id = fields.Many2one('tender_cat.tender.proposal', string='Proposal')
    proposal_desc = fields.Text()

    archive_name = fields.Char(string='Archive name')

    data = fields.Binary('File', readonly=True, attachment=False)
    state = fields.Selection([('choose', 'choose'), ('get', 'get')],  # choose arch name or get the file
                             default='choose')
    moto = fields.Text(default=_('Great! Archive is ready, you can download it now'))

    @api.model
    def default_get(self, default_fields):
        result = super(DownloadProposalWizard, self).default_get(default_fields)

        active_id = self.env.context.get('active_id')
        if active_id:
            result['proposal_id'] = active_id
            proposal = self.env['tender_cat.tender.proposal'].browse(active_id)
            result['archive_name'] = proposal.name
            result['proposal_desc'] = proposal.description

        return result

    def create_archive(self):
        this = self[0]
        pdf_ext = 'pdf'
        zip_ext = 'zip'
        arch_name = "%s.%s" % (this.archive_name, zip_ext)

        # Unload all pdf documents in temporary folder
        with tempfile.TemporaryDirectory() as dir_name:
            prop_lines = this.env['tender_cat.tender.proposal.doc.line'].search([
                ('proposal_id', '=', this.proposal_id.id),
                ('doc_class', '=', 'doc_copy'),
                ('file_content', '!=', False),
            ])
            for line in prop_lines:
                filename = '{:02d}'.format(line.line_number)+' %s.%s' % (line.doc_repr, pdf_ext)
                full_name = os.path.join(dir_name, filename)
                with open(full_name, 'wb') as pdf_file:
                    pdf_file.write(base64.b64decode(line.file_content))

            # Make archive from files in folder
            tmp_file = tempfile.NamedTemporaryFile()
            zip_folder(dir_name, tmp_file.name)

            # Save archive to binary field
            with open(tmp_file.name, 'rb') as arch_file:
                out = base64.b64encode(arch_file.read())

            tmp_file.close()

        this.write({'state': 'get', 'data': out, 'archive_name': arch_name})

        return {
            'name': _('Download proposal files'),
            'type': 'ir.actions.act_window',
            'res_model': 'tender_cat.download.proposal.wizard',
            'view_mode': 'form',
            'res_id': this.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
