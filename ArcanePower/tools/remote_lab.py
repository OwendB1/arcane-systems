"""Use the workstation's SE Remote credentials without putting them in commands/logs."""
import base64
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


def request(path, body=None, method=None):
    cfg = ET.parse(Path.home()/'.config/SpaceEngineers/Remote.cfg').getroot()
    password = cfg.findtext('AdminPassword', '')
    host = cfg.findtext('ListenIP', '127.0.0.1')
    if host not in ('127.0.0.1', 'localhost'):
        raise ValueError('This test helper only connects to the local game')
    url = 'http://127.0.0.1:'+cfg.findtext('ListenPort', '24158')+path
    auth = base64.b64encode(('admin:'+password).encode()).decode()
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
        headers={'Authorization':'Basic '+auth, 'Content-Type':'application/json'}, method=method)
    with urllib.request.urlopen(req, timeout=45) as response:
        data = response.read()
        return data if response.headers.get_content_type()=='image/png' else json.loads(data.decode('utf-8-sig'))


if __name__ == '__main__':
    result = request(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv)>2 else None)
    if isinstance(result, bytes):
        raise ValueError('Use request() and save screenshot bytes to an explicit path')
    print(json.dumps(result, indent=2))
