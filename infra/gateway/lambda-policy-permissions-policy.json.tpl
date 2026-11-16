{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PolicyKBRetrieveOnly",
      "Effect": "Allow",
      "Action": "bedrock:Retrieve",
      "Resource": "arn:aws:bedrock:${AWS_REGION}:${ACCOUNT_ID}:knowledge-base/${KB_ID}"
    },
    {
      "Sid": "OwnLogsOnly",
      "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:${AWS_REGION}:${ACCOUNT_ID}:log-group:/aws/lambda/${POLICY_LAMBDA_NAME}:*"
    }
  ]
}
