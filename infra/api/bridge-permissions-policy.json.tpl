{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeOneRuntimeOnly",
      "Effect": "Allow",
      "Action": "bedrock-agentcore:InvokeAgentRuntime",
      "Resource": ["${RUNTIME_ARN}", "${RUNTIME_ARN}/runtime-endpoint/DEFAULT"]
    },
    {
      "Sid": "OwnLogsOnly",
      "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:${AWS_REGION}:${ACCOUNT_ID}:log-group:/aws/lambda/${BRIDGE_NAME}:*"
    }
  ]
}
