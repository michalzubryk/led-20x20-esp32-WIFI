"""Import bundled graphics without changing the active scene. Uses HTTPS and prompted credentials."""
import argparse,base64,getpass,json,os,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--url',required=True,help='HTTPS base URL of your studio')
p.add_argument('--animated',action='store_true')
a=p.parse_args()
if not a.url.startswith('https://'):p.error('Use HTTPS to protect credentials')
user=os.getenv('BASIC_USER') or input('User: ')
password=os.getenv('BASIC_PASSWORD') or getpass.getpass('Password: ')
auth='Basic '+base64.b64encode(f'{user}:{password}'.encode()).decode()
def api(path,data=None):
 body=json.dumps(data).encode() if data is not None else None
 req=urllib.request.Request(a.url.rstrip('/')+path,data=body,headers={'Authorization':auth,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
known={s['name'] for s in api('/api/state')['shapes']}
filename='animated-shapes.json' if a.animated else 'shapes.json'
for shape in json.loads(Path(__file__).with_name(filename).read_text()):
 if shape['name'] in known:continue
 api('/api/shapes',shape);print('Added:',shape['name'])
