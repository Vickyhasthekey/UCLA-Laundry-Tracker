"""Repeatable Member C deployment. Run with: uv run --with boto3 --with 'botocore[crt]' infra/deploy.py."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import boto3

ROOT = Path(__file__).resolve().parents[1]


def run(*command, env=None):
    subprocess.run(command, cwd=ROOT, check=True, env=env)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', default='laundry-dev')
    parser.add_argument('--region', default='us-east-2', choices=['us-east-2'])
    parser.add_argument('--stack', default='laundry-dev')
    parser.add_argument('--frontend-dir', type=Path, help='A static production build, e.g. frontend/dist')
    parser.add_argument('--publish-only', action='store_true', help='Use an already deployed stack')
    args = parser.parse_args()
    env = {**os.environ, 'AWS_PROFILE': args.profile, 'AWS_DEFAULT_REGION': args.region, 'SAM_CLI_TELEMETRY': '0'}
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    session.client('sts').get_caller_identity()
    cf = session.client('cloudformation')
    sam = ['sam', 'deploy', '--stack-name', args.stack, '--region', args.region,
           '--profile', args.profile, '--resolve-s3', '--capabilities', 'CAPABILITY_IAM',
           '--no-confirm-changeset', '--no-fail-on-empty-changeset']
    if not args.publish_only:
        # Preserve the deployed origin during updates; never briefly reset it to localhost.
        existing = any(stack['StackName'] == args.stack and stack['StackStatus'] != 'DELETE_COMPLETE'
                       for page in cf.get_paginator('list_stacks').paginate()
                       for stack in page['StackSummaries'])
        initial_parameters = []
        if existing:
            current = {v['OutputKey']: v['OutputValue'] for v in cf.describe_stacks(StackName=args.stack)['Stacks'][0].get('Outputs', [])}
            if current.get('WebsiteUrl'):
                initial_parameters = ['--parameter-overrides', 'AllowedOrigin=' + current['WebsiteUrl']]
        run('sam', 'validate', '--lint', '--template-file', 'infra/template.yaml', env=env)
        run('sam', 'build', '--template-file', 'infra/template.yaml', env=env)
        run(*sam, *initial_parameters, env=env)
    outputs = {v['OutputKey']: v['OutputValue'] for v in cf.describe_stacks(StackName=args.stack)['Stacks'][0]['Outputs']}
    if not args.publish_only:
        run(*sam, '--parameter-overrides', 'AllowedOrigin=' + outputs['WebsiteUrl'], env=env)
    db = session.resource('dynamodb')
    # Only seed the explicitly isolated integration fixture. No real inventory.
    if not args.frontend_dir:
        db.Table(outputs['RoomsTable']).put_item(Item={'roomId': 'demo-room', 'name': 'Demo laundry room', 'residenceHall': 'DEMO', 'dataMode': 'demo'})
        for code, kind, label in [('W01', 'washer', 'Demo washer 01'), ('D01', 'dryer', 'Demo dryer 01')]:
            db.Table(outputs['MachinesTable']).put_item(Item={'roomId': 'demo-room', 'machineId': 'demo-room:' + code, 'code': 'demo' + code.lower(), 'type': kind, 'label': label, 'dataMode': 'demo'})
    with tempfile.TemporaryDirectory(prefix='laundry-publish-') as temporary:
        build = Path(temporary) / 'site'
        source = args.frontend_dir.resolve() if args.frontend_dir else ROOT / 'infra/demo/frontend'
        if not (source / 'index.html').exists():
            raise ValueError('Frontend build must contain index.html')
        shutil.copytree(source, build)
        if not args.frontend_dir:
            (build / 'config.js').write_text('window.API_BASE_URL = ' + json.dumps(outputs['ApiUrl']) + ';\n')
        run('aws', 's3', 'sync', str(build), 's3://' + outputs['WebsiteBucket'], '--cache-control', 'max-age=0,no-cache', env=env)
    # Do not delete historical objects or data during a deployment.
    session.client('cloudfront').create_invalidation(DistributionId=outputs['DistributionId'], InvalidationBatch={'Paths': {'Quantity': 1, 'Items': ['/*']}, 'CallerReference': __import__('uuid').uuid4().hex})
    # Secrets are not fetched here. Even the secret ARN is omitted from the report.
    public = {k: v for k, v in outputs.items() if 'Secret' not in k}
    (ROOT / 'infra/deployment-state.json').write_text(json.dumps(public, indent=2) + '\n')
    print('Website:', outputs['WebsiteUrl'])
    print('API:', outputs['ApiUrl'])


if __name__ == '__main__':
    main()
