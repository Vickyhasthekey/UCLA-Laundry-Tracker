"""Exercise real boto3 calls against Moto's in-memory AWS implementation."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

import boto3
from moto import mock_aws


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.mock = mock_aws()
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.env = patch.dict(os.environ, {'AWS_DEFAULT_REGION': 'us-east-2', 'ROOMS_TABLE': 'rooms', 'MACHINES_TABLE': 'machines', 'REPORTS_TABLE': 'reports', 'RATE_LIMIT_TABLE': 'limits'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.db = boto3.resource('dynamodb')
        for name, keys in [('rooms', ['roomId']), ('machines', ['roomId', 'machineId']), ('reports', ['machineId', 'reportKey']), ('limits', ['bucketKey'])]:
            self.db.create_table(TableName=name, BillingMode='PAY_PER_REQUEST', AttributeDefinitions=[{'AttributeName': key, 'AttributeType': 'S'} for key in keys], KeySchema=[{'AttributeName': key, 'KeyType': 'HASH' if i == 0 else 'RANGE'} for i, key in enumerate(keys)])
        arn = boto3.client('secretsmanager').create_secret(Name='test-device', SecretString='test-only-secret')['ARN']
        os.environ['DEVICE_HASH_SECRET_ARN'] = arn
        self.db.Table('machines').put_item(Item={'roomId': 'demo', 'machineId': 'demo:W01'})
        spec = importlib.util.spec_from_file_location('demo_app', Path(__file__).resolve().parents[1] / 'demo/backend/app.py')
        self.app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.app)
        self.device = str(uuid.uuid4())

    def send(self, body=None, device=None, machine='demo:W01', method='POST', ip='192.0.2.1'):
        return self.app.handler({'routeKey': method + ' /machines/{machineId}/reports', 'pathParameters': {'machineId': machine}, 'headers': {'X-Device-Id': self.device if device is None else device}, 'requestContext': {'http': {'sourceIp': ip}}, 'body': json.dumps(body if body is not None else {'issueType': 'OTHER'})}, None)

    def test_save_private_hash_and_consistent_read(self):
        r = self.send()
        self.assertEqual(r['statusCode'], 201)
        self.assertNotIn('deviceHash', json.loads(r['body']))
        raw = self.db.Table('reports').scan()['Items'][0]
        self.assertEqual(len(raw['deviceHash']), 64)
        self.assertNotIn(self.device, json.dumps(raw))
        history = json.loads(self.send(method='GET')['body'])['items']
        self.assertEqual(len(history), 1)
        self.assertNotIn('deviceHash', history[0])

    def test_cooldown_and_atomic_failure(self):
        self.assertEqual(self.send()['statusCode'], 201)
        self.assertEqual(self.send()['statusCode'], 429)
        self.assertEqual(len(self.db.Table('reports').scan()['Items']), 1)
        counters = [x['count'] for x in self.db.Table('limits').scan()['Items'] if 'count' in x]
        self.assertEqual(counters, [1, 1])

    def test_expired_cooldown_works_without_ttl_deletion(self):
        with patch.object(self.app.time, 'time', return_value=1800000000):
            self.assertEqual(self.send()['statusCode'], 201)
        with patch.object(self.app.time, 'time', return_value=1800000180):
            self.assertEqual(self.send()['statusCode'], 201)

    def test_daily_device_limit(self):
        for i in range(30):
            with patch.object(self.app.time, 'time', return_value=1800000000 + i * 181):
                self.assertEqual(self.send()['statusCode'], 201)
        with patch.object(self.app.time, 'time', return_value=1800000000 + 30 * 181):
            self.assertEqual(self.send()['statusCode'], 429)

    def test_ip_limit_and_day_rollover(self):
        now = 1800000000
        day = now // 86400
        ip_hash = self.app.fingerprint('ip:192.0.2.1')
        self.db.Table('limits').put_item(Item={'bucketKey': f'ip:{ip_hash}:{day}', 'count': 300, 'expiresAt': (day + 1) * 86400})
        with patch.object(self.app.time, 'time', return_value=now):
            self.assertEqual(self.send()['statusCode'], 429)
        with patch.object(self.app.time, 'time', return_value=(day + 1) * 86400):
            self.assertEqual(self.send()['statusCode'], 201)

    def test_reject_invalid_and_unknown(self):
        for body in [[], {'issueType': []}, {'issueType': 'INVALID'}, {'issueType': 'OTHER', 'note': 'no free text'}, {'issueType': 'OTHER', 'website': 'spam'}]:
            self.assertEqual(self.send(body)['statusCode'], 400)
        self.assertEqual(self.send(device='bad')['statusCode'], 400)
        self.assertEqual(self.send(machine='demo:missing')['statusCode'], 404)
        self.assertEqual(self.db.Table('reports').scan()['Items'], [])


if __name__ == '__main__':
    unittest.main()
