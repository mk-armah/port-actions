import requests
import datetime
import base64
from urllib.parse import quote
import os

def main(owner_repo, workflows, branch, number_of_days, pat_token="", actions_token="", app_id="", app_installation_id="", app_private_key=""):
    owner, repo = owner_repo.split('/')
    workflows_array = workflows.split(',')
    print(f"Owner/Repo: {owner}/{repo}")
    print(f"Workflows: {workflows}")
    print(f"Branch: {branch}")
    print(f"Number of days: {number_of_days}")

    auth_header = get_auth_header(pat_token, actions_token, app_id, app_installation_id, app_private_key)

    uri = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if auth_header:
        headers.update(auth_header)

    response = requests.get(uri, headers=headers)
    if response.status_code == 404:
        print("Repo is not found or you do not have access")
        return

    workflows_response = response.json()
    workflow_ids = []
    workflow_names = []

    for workflow in workflows_response['workflows']:
        if workflow['name'] in workflows_array and workflow['id'] not in workflow_ids:
            workflow_ids.append(workflow['id'])
            workflow_names.append(workflow['name'])

    date_list = []
    unique_dates = set()
    deployments_per_day_list = []

    for workflow_id in workflow_ids:
        uri = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs?per_page=100&status=completed"
        response = requests.get(uri, headers=headers)
        workflow_runs_response = response.json()

        for run in workflow_runs_response['workflow_runs']:
            run_date = datetime.datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            if run['head_branch'] == branch and run_date > datetime.datetime.now() - datetime.timedelta(days=number_of_days):
                date_list.append(run_date)
                unique_dates.add(run_date.date())

    if date_list:
        deployments_per_day = len(date_list) / number_of_days
        deployments_per_day_list.append(deployments_per_day)

    if deployments_per_day_list:
        total_deployments = sum(deployments_per_day_list)
        deployments_per_day = total_deployments / len(deployments_per_day_list)
    else:
        deployments_per_day = 0

    print(f"Deployment frequency over the last {number_of_days} days is {deployments_per_day} per day")

def get_auth_header(pat_token, actions_token, app_id, app_installation_id, app_private_key):
    if pat_token:
        token_bytes = pat_token.encode('utf-8')
        base64_bytes = base64.b64encode(token_bytes)
        return {"Authorization": f"Basic {base64_bytes.decode('utf-8')}"}
    elif actions_token:
        return {"Authorization": f"Bearer {actions_token}"}
    elif app_id:
        # GitHub App authentication is more complex and involves generating a JWT. This is a placeholder for the logic.
        return {"Authorization": "Bearer generated_app_token"}
    else:
        return None

if __name__ == "__main__":
    owner_repo = os.getenv('REPOSITORY')
    token = os.getenv('GITHUB_TOKEN')  # Your personal access token or GitHub App token
    workflows = 'Apply release,Release framework,Sonarcloud scan integrations'
    branch = 'main'
    time_frame = int(os.getenv('TIMEFRAME_IN_DAYS'))
    number_of_days = 30 if not time_frame else time_frame
    
    main(owner_repo, workflows, branch, number_of_days, pat_token=token)
