from odoo import http
from odoo.http import request
import requests
import json

MICROSOFT_GRAPH_END_POINT = "https://graph.microsoft.com"


class OnedriveAuth(http.Controller):

    @http.route('/onedrive/authentication', type='http', auth="public")
    def oauth2callback(self, **kw):
        return request.make_response(json.dumps(kw), headers=[('Content-Type', 'application/json')])

    @http.route(['/onedrive/checkfolder/<model("one_drive.config"):config_id>',], type='http', auth="user", csrf=False)
    def get_checkfolder(self, config_id=None, **args):
        headers = self.get_one_drive_header(config_id)
        url = (
            f"{MICROSOFT_GRAPH_END_POINT}/v1.0"
            f"/users/{config_id.drive_user_id}/drive/root/search(q='{config_id.folder_name}')"
        )
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
        except Exception as e:
            data = str(e)
        return request.make_response(
            json.dumps(data, indent=4),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(['/onedrive/user_info/<model("one_drive.config"):config_id>'], type='http', auth="user", csrf=False)
    def get_user_info(self, config_id=None, **args):
        headers = self.get_one_drive_header(config_id)
        url = f"{MICROSOFT_GRAPH_END_POINT}/v1.0/me/drive"
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
        except Exception as e:
            data = str(e)
        return request.make_response(
            json.dumps(data, indent=4),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route(['/onedrive/folder_info/<model("one_drive.config"):config_id>',], type='http', auth="user", csrf=False)
    def get_folder_info(self, config_id=None, **args):
        headers = self.get_one_drive_header(config_id)
        url = (
            f"{MICROSOFT_GRAPH_END_POINT}/v1.0"
            f"/drives/{config_id.drive_id}/items/{config_id.folder_id}"
        )
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
        except Exception as e:
            data = str(e)
        return request.make_response(
            json.dumps(data, indent=4),
            headers=[('Content-Type', 'application/json')]
        )

    def get_one_drive_header(self, config_id):
        return {
            'Authorization': f'Bearer {config_id.access_token}',
            'Content-Type': 'application/json'
        }