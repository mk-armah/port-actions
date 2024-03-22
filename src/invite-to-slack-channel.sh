#!/bin/bash

# Slack API token (xoxp- or xoxb-)
SLACK_TOKEN="xoxp-your-slack-token"

# The name of the channel you want to find and invite users to
CHANNEL_NAME="desired-channel-name"

# User emails to invite, separated by spaces
USER_EMAILS=("user1@example.com" "user2@example.com")

# Function to find a Slack channel by name and return its ID
get_channel_id_by_name() {
    local channel_name=$1
    local channels=$(curl -s -X GET "https://slack.com/api/conversations.list" \
        -H "Authorization: Bearer $SLACK_TOKEN" \
        -H "Content-Type: application/x-www-form-urlencoded")

    echo $(echo $channels | jq -r --arg CHANNEL_NAME "$channel_name" '.channels[] | select(.name==$CHANNEL_NAME) | .id')
}

# Function to find a user ID by their email address
get_user_id_by_email() {
    local user_email=$1
    local user=$(curl -s -X GET "https://slack.com/api/users.lookupByEmail" \
        -H "Authorization: Bearer $SLACK_TOKEN" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "email=$user_email")

    echo $(echo $user | jq -r '.user.id')
}

# Function to invite users to a Slack channel
invite_users_to_channel() {
    local channel_id=$1
    shift
    local user_ids=("$@")
    local user_ids_string=$(IFS=,; echo "${user_ids[*]}")

    local result=$(curl -s -X POST "https://slack.com/api/conversations.invite" \
        -H "Authorization: Bearer $SLACK_TOKEN" \
        -H "Content-Type: application/json" \
        --data "{\"channel\":\"$channel_id\",\"users\":\"$user_ids_string\"}")

    echo $result
}

# Main script logic
channel_id=$(get_channel_id_by_name "$CHANNEL_NAME")

if [ -n "$channel_id" ]; then
    echo "Found channel ID for '$CHANNEL_NAME': $channel_id"

    user_ids=()
    for email in "${USER_EMAILS[@]}"; do
        user_id=$(get_user_id_by_email "$email")
        if [ -n "$user_id" ]; then
            user_ids+=("$user_id")
        else
            echo "No user found for email $email"
        fi
    done

    if [ ${#user_ids[@]} -eq 0 ]; then
        echo "No users found."
        exit 1
    fi

    invite_result=$(invite_users_to_channel "$channel_id" "${user_ids[@]}")
    echo "Invite result: $invite_result"
else
    echo "Channel '$CHANNEL_NAME' not found."
fi
