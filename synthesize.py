import boto3

polly = boto3.client('polly')

with open('speech.txt', 'r') as f:
    text_to_synthesize = f.read()

response = polly.synthesize_speech(
    LanguageCode='en-US',
    OutputFormat='mp3',
    Text=text_to_synthesize,
    VoiceId='Matthew'
)

with open ("polly_output.mp3", "wb") as f:
    f.write(response["AudioStream"].read())
