import requests
from datetime import datetime, timedelta
import base64
import json
import os

def main(owner_repo, workflows, branch, number_of_days, commit_counting_method="last", pat_token="", actions_token="", app_id="", app_installation_id="", app_private_key=""):
    owner, repo = owner_repo.split('/')
    workflows_array = workflows.split(',')
    if commit_counting_method == "":
        commit_counting_method = "last"
    print(f"Owner/Repo: {owner}/{repo}")
    print(f"Number of days: {number_of_days}")
    print(f"Workflows: {workflows_array[0]}")
    print(f"Branch: {branch}")
    print(f"Commit counting method '{commit_counting_method}' being used")

    auth_header = get_auth_header(pat_token, actions_token, app_id, app_installation_id, app_private_key)

    prs_response = get_pull_requests(owner, repo, branch, auth_header)
    pr_processing_result = process_pull_requests(prs_response, number_of_days, commit_counting_method, owner, repo, auth_header)

    workflows_response = get_workflows(owner, repo, auth_header)
    workflow_processing_result = process_workflows(workflows_response, workflows_array, owner, repo, branch, number_of_days, auth_header)

    return evaluate_lead_time(pr_processing_result, workflow_processing_result, number_of_days)

def get_auth_header(pat_token, actions_token, app_id, app_installation_id, app_private_key):
    headers = {}
    if pat_token:
        encoded_credentials = base64.b64encode(f":{pat_token}".encode()).decode()
        headers['Authorization'] = f"Basic {encoded_credentials}"
    elif actions_token:
        headers['Authorization'] = f"Bearer {actions_token}"
    # Add more authentication methods as needed
    return headers

def get_pull_requests(owner, repo, branch, headers):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&head={branch}&per_page=100&state=closed"
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        print("Repo is not found or you do not have access")
        exit()
    return response.json()

def process_pull_requests(prs, number_of_days, commit_counting_method, owner, repo, headers):
    pr_counter = 0
    total_pr_hours = 0
    for pr in prs:
        merged_at = pr.get('merged_at')
        if merged_at and datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ") > datetime.utcnow() - timedelta(days=number_of_days):
            pr_counter += 1
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr['number']}/commits?per_page=100"
            commits_response = requests.get(commits_url, headers=headers).json()
            if commits_response:
                if commit_counting_method == "last":
                    start_date = commits_response[-1]['commit']['committer']['date']
                elif commit_counting_method == "first":
                    start_date = commits_response[0]['commit']['committer']['date']
                start_date = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ")
                merged_at = datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ")
                duration = merged_at - start_date
                total_pr_hours += duration.total_seconds() / 3600
    return pr_counter, total_pr_hours

def get_workflows(owner, repo, headers):
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows"
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        print("Repo is not found or you do not have access")
        exit()
    return response.json()

def process_workflows(workflows_response, workflow_names, owner, repo, branch, number_of_days, headers):
    workflow_ids = [wf['id'] for wf in workflows_response['workflows'] if wf['name'] in workflow_names]
    total_workflow_hours = 0
    workflow_counter = 0
    for workflow_id in workflow_ids:
        runs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs?per_page=100&status=completed"
        runs_response = requests.get(runs_url, headers=headers).json()
        for run in runs_response['workflow_runs']:
            if run['head_branch'] == branch and datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ") > datetime.utcnow() - timedelta(days=number_of_days):
                workflow_counter += 1
                start_time = datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                end_time = datetime.strptime(run['updated_at'], "%Y-%m-%dT%H:%M:%SZ")
                duration = end_time - start_time
                total_workflow_hours += duration.total_seconds() / 3600
    return workflow_counter, total_workflow_hours

def calculate_rating(lead_time_for_changes_in_hours):
    daily_deployment=24
    weekly_deployment=24*7
    monthly_deployment=24*30
    every_six_months_deployment=24*30*6
    
    if lead_time_for_changes_in_hours <= 0:
        rating = "None"
        color = "lightgrey"
    elif lead_time_for_changes_in_hours < 1:
        rating = "Elite"
        color = "brightgreen"
    elif lead_time_for_changes_in_hours <= daily_deployment:
        rating = "Elite"
        color = "brightgreen"
    elif daily_deployment < lead_time_for_changes_in_hours <= weekly_deployment:
        rating = "High"
        color = "green"
    elif weekly_deployment < lead_time_for_changes_in_hours <= monthly_deployment:
        rating = "High"
        color = "green"
    elif monthly_deployment < lead_time_for_changes_in_hours <= every_six_months_deployment:
        rating = "Medium"
        color = "yellow"
    else: 
        # lead_time_for_changes_in_hours > every_six_months_deployment
        rating = "Low"
        color = "red"
        
    display_metric = round(lead_time_for_changes_in_hours, 2)
    display_unit = "hours"
        
    return {
        "rating": rating,
        "color": color,
        "display_metric": display_metric,
        "display_unit": display_unit
    }


def evaluate_lead_time(pr_result, workflow_result, number_of_days):
    pr_counter, total_pr_hours = pr_result
    workflow_counter, total_workflow_hours = workflow_result
    if pr_counter == 0:
        pr_counter = 1
    if workflow_counter == 0:
        workflow_counter = 1
    pr_average = total_pr_hours / pr_counter
    workflow_average = total_workflow_hours / workflow_counter
    lead_time_for_changes_in_hours = pr_average + workflow_average
    print(f"PR average time duration: {pr_average} hours")
    print(f"Workflow average time duration: {workflow_average} hours")
    print(f"Lead time for changes in hours: {lead_time_for_changes_in_hours}")

    report = {
            "pr_average_time_duration" : round(pr_average,2),
            "workflow_average_time_duration" : round(workflow_average,2),
            "lead_time_for_changes_in_hours": round(lead_time_for_changes_in_hours,2)
    }
    rating = calculate_rating(lead_time_for_changes_in_hours)
    report.update(rating)
    
    return json.dumps(report, default=str)
    
if __name__ == "__main__":
    owner_repo = os.getenv('REPOSITORY')
    token = os.getenv('GITHUB_TOKEN')  # Your personal access token or GitHub App token
    workflows = os.getenv('WORKFLOWS')
    branch = 'main'
    time_frame = int(os.getenv('TIMEFRAME_IN_DAYS'))
    number_of_days = 30 if not time_frame else time_frame
    
    report = main(owner_repo, workflows, branch, number_of_days)
    with open(os.getenv('GITHUB_ENV'), 'a') as github_env:
        github_env.write(f"lead_time_for_changes_report={report}\n")
