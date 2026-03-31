from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class IrAttachments(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            if self.env.user.one_drive_config_id and rec.res_model and rec.res_id:
                self.env.user.one_drive_config_id.upload_session(rec)
        return res

class ResUsers(models.Model):
    _inherit = 'res.users'

    one_drive_config_id = fields.Many2one('one_drive.config', domain="[('user_id', '=', id)]")

