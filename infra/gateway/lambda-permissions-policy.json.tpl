{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "OrdersTableReadOne",
      "Effect": "Allow",
      "Action": "dynamodb:GetItem",
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${ORDERS_TABLE}"
    },
    {
      "Sid": "OwnLogsOnly",
      "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:${AWS_REGION}:${ACCOUNT_ID}:log-group:/aws/lambda/${LAMBDA_NAME}:*"
    }
  ]
}
