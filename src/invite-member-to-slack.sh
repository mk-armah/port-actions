#!/bin/bash

# Input parameters
clientId="$1"
clientSecret="$2"
SLACK_TOKEN="$3"
CHANNEL_ID="$4"
MEMBER_EMAILS="$5"

# Function to report errors
report_error() {
  local message="$1"
  echo "$message"
  # Reporting error to Port - ensure PORT_ACCESS_TOKEN is available
  curl -s -X POST "https://api.getport.io/v1/actions/runs/$run_id/logs" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $PORT_ACCESS_TOKEN" \
    -d "{\"message\": \"$message\"}"
}

# Step 1: Get the Port access token
PORT_TOKEN_RESPONSE=$(curl -s -X 'POST' \
  'https://api.getport.io/v1/auth/access_token' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d "{
        \"clientId\": \"$clientId\",
        \"clientSecret\": \"$clientSecret\"
      }")

PORT_ACCESS_TOKEN=$(echo $PORT_TOKEN_RESPONSE | jq -r '.accessToken')

# Ensure the access token was obtained successfully
if [ -z "$PORT_ACCESS_TOKEN" ] || [ "$PORT_ACCESS_TOKEN" == "null" ]; then
  echo "Failed to obtain Port access token ❌"
  exit 1
fi

# Step 2: Iterate over the emails and add members
user_ids=""
IFS=',' read -ra ADDR <<< "$MEMBER_EMAILS"
for email in "${ADDR[@]}"; do
  user_response=$(curl -s -X GET "https://slack.com/api/users.lookupByEmail?email=$email" \
    -H "Authorization: Bearer $SLACK_TOKEN")

  if [[ "$(echo $user_response | jq -r '.ok')" == "true" ]]; then
    user_id=$(echo $user_response | jq -r '.user.id')
    user_ids+="${user_id},"
  else
    error_message="Failed to retrieve user id for $email: $(echo $user_response | jq -r '.error' | tr '_' ' ') ⚠️"
    report_error "$error_message"
  fi
done

user_ids=${user_ids%,}

if [[ -n "$user_ids" ]]; then
  invite_response=$(curl -s -X POST "https://slack.com/api/conversations.invite" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $SLACK_TOKEN" \
    --data "{\"channel\":\"$CHANNEL_ID\",\"users\":\"$user_ids\"}")

  if [[ "$(echo $invite_response | jq -r '.ok')" == "false" ]]; then
    error_message="Failed to invite users to channel: $(echo $invite_response | jq -r '.error' | tr '_' ' ') ⚠️"
    report_error "$error_message"
  fi
else
  report_error "No user IDs found to invite."
fi
