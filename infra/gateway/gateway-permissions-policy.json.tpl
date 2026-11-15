{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeGetOrderLambdaOnly",
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${LAMBDA_NAME}"
    }
  ]
}
