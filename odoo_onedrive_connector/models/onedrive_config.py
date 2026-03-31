import json
from odoo import models, fields, api, _
from datetime import timedelta
import base64
import requests
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import ValidationError

MAX_SIMPLE_UPLOAD = 4 * 1024 * 1024
ONEDRIVE_SCOPE = 'offline_access openid Files.ReadWrite.All User.Read.All'
MICROSOFT_GRAPH_END_POINT = "https://graph.microsoft.com"
TENANT_BASE_URL = "https://login.microsoftonline.com"


class OneDriveConfig(models.Model):
    _name = 'one_drive.config'
    _description = 'One Drive Configuration'

    name = fields.Char()
    tenant_id = fields.Char()
    code = fields.Char()
    client_id = fields.Char()
    client_secret = fields.Char()
    access_token = fields.Char()
    refresh_token = fields.Char()
    redirect_uri = fields.Char(compute="_compute_redirect_uri")
    folder_name = fields.Char()
    drive_id = fields.Char(string="Drive ID")
    folder_id = fields.Char(string="Folder ID")
    drive_user_id = fields.Char(string="Drive User ID")
    user_id = fields.Many2one('res.users', string="Responsible")
    token_expiry = fields.Datetime( string="Token Expiry" )
    one_drive_history_ids = fields.One2many('one_drive.history', 'one_drive_config_id')
    drive_status = fields.Selection([
        ('connected', 'Connected'),
        ('disconnected', 'DisConnected'),
    ], compute="_compute_connection_status")
    active = fields.Boolean()

    @api.model
    def default_get(self, field_values):
        context = self.env.context
        res = super().default_get(field_values)
        if 'params' in context and  'resId' in context.get('params'):
            res['user_id'] = context.get('params')['resId']
        return res

    @api.constrains('user_id')
    def restrict_user(self):
        for rec in self:
            if rec.user_id and rec.user_id.one_drive_config_id:
                    raise ValidationError(_("Sorry, For This User One Drive Configuration Already Done"))
            else:
                rec.user_id.one_drive_config_id = rec.id

    def deactivate_configuration(self):
        self.active = False
    def activate_configuration(self):
        self.active = True

    def _compute_redirect_uri(self):
        for rec in self:
            rec.redirect_uri = self.get_base_url() + '/onedrive/authentication'

    def _compute_connection_status(self):
        for rec in self:
            if rec.token_expiry and (fields.Datetime.now() < rec.token_expiry) and rec.access_token and rec.active:
                rec.drive_status = 'connected'
            else:
                rec.drive_status = 'disconnected'

    def make_connection(self):
        url = f"{TENANT_BASE_URL}/{self.tenant_id}/oauth2/v2.0/authorize?client_id={self.client_id}&scope={ONEDRIVE_SCOPE}&response_type=code"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def get_access_token(self):
        base_url = self.get_base_url()
        headers = { "Content-Type": "application/x-www-form-urlencoded" }
        data = {
            "code": self.code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": ONEDRIVE_SCOPE,
            'redirect_uri': f"{base_url}/onedrive/authentication",
            "grant_type": "authorization_code",
        }
        tenant_url = f"{TENANT_BASE_URL}/{self.tenant_id}/oauth2/v2.0/token"
        try:
            response = requests.post(tenant_url,  data=data, headers=headers)
            data = response.json()
            if response.status_code == 200:
                self.refresh_token = data['refresh_token']
                self.access_token = data['access_token']
                self.token_expiry = fields.Datetime.now() + timedelta(seconds=data.get("expires_in"))
            else:
                raise ValidationError(_(f"Connection Failed Returned response {response.status_code}\n"
                                        f"Error Status: {data}"))
        except Exception as e :
            raise ValidationError(_(f"Connection Failed : {str(e)}"))

    def revoke_access_token(self):
        base_url = self.get_base_url()
        tenant_url = f"{TENANT_BASE_URL}/{self.tenant_id}/oauth2/v2.0/token"
        headers = {"Content-type": "application/x-www-form-urlencoded"}
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            'scope': ONEDRIVE_SCOPE,
            'grant_type': "refresh_token",
            'redirect_uri': f"{base_url}/onedrive/authentication",
            "refresh_token" : self.refresh_token,
        }
        try:
            response = requests.post(tenant_url, data=data, headers=headers)
            data = response.json()
            if response.status_code == 200:
                access_token = data.get("access_token")
                expires_in = data.get("expires_in")
                if access_token:
                    self.access_token = access_token
                    self.token_expiry = fields.Datetime.now() + timedelta(seconds=expires_in)
            else:
                self.create_history('error', False, str(data))
        except Exception as e :
            self.create_history('error', False, str(e))
            self.message_post(
                body=str(e),
                message_type='comment',
                author_id=self.env.user.partner_id.id,
                body_is_html=True
            )


    def check_folders(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/onedrive/checkfolder/%s' % (self.id),
            'target': 'new',
        }

    def get_folder_info(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/onedrive/folder_info/%s' % (self.id),
            'target': 'new',
        }

    def get_user_id(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/onedrive/user_info/%s' % (self.id),
            'target': 'new',
        }

    def verify_token(self):
        if self.token_expiry <= fields.Datetime.now():
            self.revoke_access_token()

    def upload_session(self, attachment):
        self.verify_token()

        try:
            file_data = base64.b64decode(attachment.datas)
            file_size = len(file_data)
            if file_size <= MAX_SIMPLE_UPLOAD:
                self._upload_direct(attachment, file_data)
            else:
                self._upload_large_file(attachment, file_data)
            self.create_history('success', attachment)
        except Exception as e:
            self.create_history('error', attachment, f"Attachment Upload Failed : Error Occured During Sending File to OneDrive\n err: {str(e)}")
            record = self.env[attachment.res_model].browse(attachment.res_id)
            record.message_post(
                body=f"Sending File To OneDrive Failed: {str(e)}",
                partner_ids=self.env.user.partner_id.ids,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def _upload_direct(self, attachment, file_data):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/octet-stream",
        }

        url = (
            f"{MICROSOFT_GRAPH_END_POINT}/v1.0/drives/"
            f"{self.drive_id}/items/"
            f"{self.folder_id}:/{attachment.name}:/content"
        )
        response = requests.put(url, headers=headers, data=file_data,  timeout=120 )
        response.raise_for_status()

    def _upload_large_file(self, attachment, file_data):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        upload_session_url = (
            f"{MICROSOFT_GRAPH_END_POINT}/v1.0/drives/"
            f"{self.drive_id}/items/"
            f"{self.folder_id}:/{attachment.name}:/createUploadSession"
        )

        upload_session = requests.post(upload_session_url, headers=headers)
        upload_session.raise_for_status()
        upload_url = upload_session.json().get("uploadUrl")
        if not upload_url:
            raise ValueError("Upload URL missing")

        file_size = len(file_data)
        upload_headers = {
            "Content-Length": str(file_size),
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
        }
        response = requests.put(
            upload_url,
            headers=upload_headers,
            data=file_data,
            timeout=300
        )
        response.raise_for_status()
        _logger.info("Large file upload success")

    def create_history(self, status, attachment, error=None):
        vals = {
            'one_drive_config_id': self.id,
            'file_name': attachment.name if attachment else 'Authentication Error',
            'status': status,
            'error': error,
            'attachment_id': [(4, attachment.id)] if attachment else []
        }
        self.env['one_drive.history'].create(vals)


class OneDriveHistory(models.Model):
    _name = 'one_drive.history'

    one_drive_config_id = fields.Many2one('one_drive.config')
    file_name = fields.Char(string="File Name")
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
    ])
    error = fields.Text()
    attachment_id = fields.Many2many('ir.attachment')
