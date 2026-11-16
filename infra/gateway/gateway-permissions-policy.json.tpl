{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeToolLambdasOnly",
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": [
        "arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${LAMBDA_NAME}",
        "arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${POLICY_LAMBDA_NAME}"
      ]
    }
  ]
}
