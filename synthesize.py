import boto3
import os
from contextlib import closing
import json


def lambda_handler(event, context):

    bucket = os.environ["S3_Bucket"]
    prefix = os.environ.get("S3_Bucket_Prefix", "")
    result = synthesize(bucket, prefix)

    return {
        "statusCode": 200,
        "body": json.dumps({"bucket": bucket, "prefix": prefix})
    }


def synthesize(bucket:str, prefix:str):
    s3 = boto3.client('s3')
    polly = boto3.client('polly')

    with open('speech.txt', 'r') as f:
        text_to_synthesize = f.read()

    response = polly.synthesize_speech(
        LanguageCode='en-US',
        OutputFormat='mp3',
        Text=text_to_synthesize,
        VoiceId='Matthew'
    )

    with closing(response["AudioStream"]) as stream:
        audio_bytes = stream.read()

    s3.put_object(Bucket=bucket, Key=prefix, Body=audio_bytes)
    return {'bucket':bucket, 'key':prefix}