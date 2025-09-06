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

    key_prefix = prefix.strip("/")                         
    text_key   = f"{key_prefix}/speech.txt" if key_prefix else "speech.txt"  
    obj = s3.get_object(Bucket=bucket, Key=text_key)
    text_to_synthesize = obj["Body"].read().decode("utf-8") 


    response = polly.synthesize_speech(
        LanguageCode='en-US',
        OutputFormat='mp3',
        Text=text_to_synthesize,
        VoiceId='Matthew'
    )

    with closing(response["AudioStream"]) as stream:
        audio_bytes = stream.read()

    output_key = f"{key_prefix}/speech.mp3" if key_prefix else "speech.mp3"
    s3.put_object(Bucket=bucket, Key=output_key, Body=audio_bytes, ContentType="audio/mpeg")
    return {'bucket':bucket, 'key':output_key}