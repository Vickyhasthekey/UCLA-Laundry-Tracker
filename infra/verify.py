"""Live, bounded integration checks. Writes one clearly marked demo report."""
import json
import ssl
import certifi
from pathlib import Path
import urllib.error
import urllib.request
import uuid
import time


def request(url, method='GET', data=None, headers=None):
    time.sleep(0.3)  # Stay below the shared API's five-request/second throttle.
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context(cafile=certifi.where())) as result:
            return result.status, dict(result.headers), result.read().decode()
    except urllib.error.HTTPError as error:
        with error:
            return error.code, dict(error.headers), error.read().decode()


def main():
    state = json.loads((Path(__file__).parent / 'deployment-state.json').read_text())
    api, site = state['ApiUrl'], state['WebsiteUrl']
    headers = {'Content-Type': 'application/json', 'X-Device-Id': str(uuid.uuid4())}
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
        print('PASS:', name)

    check('health', request(api + '/health')[0] == 200)
    check('rooms', request(api + '/rooms')[0] == 200)
    check('machine inventory', request(api + '/rooms/demo-room/machines')[0] == 200)
    path = api + '/machines/demo-room:W01/reports'
    check('missing device rejected', request(path, 'POST', {'issueType': 'OTHER'})[0] == 400)
    check('invalid choice rejected', request(path, 'POST', {'issueType': 'INVALID'}, headers)[0] == 400)
    check('honeypot rejected', request(path, 'POST', {'issueType': 'OTHER', 'website': 'spam'}, headers)[0] == 400)
    check('free text rejected', request(path, 'POST', {'issueType': 'OTHER', 'note': 'test'}, headers)[0] == 400)
    check('unknown machine rejected', request(api + '/machines/demo-room:missing/reports', 'POST', {'issueType': 'OTHER'}, headers)[0] == 404)
    code, _, body = request(path, 'POST', {'issueType': 'OTHER'}, headers)
    check('demo report saved', code == 201)
    report = json.loads(body)
    check('immediate duplicate blocked', request(path, 'POST', {'issueType': 'OTHER'}, headers)[0] == 429)
    code, _, body = request(path)
    check('saved report visible immediately', code == 200 and any(item['reportId'] == report['reportId'] for item in json.loads(body)['items']))
    check('device identifiers not exposed', 'deviceHash' not in body and headers['X-Device-Id'] not in body)
    preflight = {'Origin': site, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type,x-device-id'}
    code, response_headers, _ = request(path, 'OPTIONS', headers=preflight)
    response_headers = {key.lower(): value for key, value in response_headers.items()}
    check('CORS permits site and device header', code in (200, 204) and response_headers.get('access-control-allow-origin') == site and 'x-device-id' in response_headers.get('access-control-allow-headers', '').lower())
    preflight['Origin'] = 'https://untrusted.example'
    _, response_headers, _ = request(path, 'OPTIONS', headers=preflight)
    check('CORS does not permit unrelated origin', not any(key.lower() == 'access-control-allow-origin' for key in response_headers))
    code, _, body = request(site)
    check('HTTPS demo website', code == 200 and 'AWS integration demo' in body)
    code, _, _ = request('https://' + state['WebsiteBucket'] + '.s3.us-east-2.amazonaws.com/index.html')
    check('direct S3 denied', code == 403)
    (Path(__file__).parent / 'verification-results.json').write_text(json.dumps({'checks': checks, 'result': 'PASS'}, indent=2) + '\n')


if __name__ == '__main__':
    main()
