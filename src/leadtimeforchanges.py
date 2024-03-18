from github import Github
from datetime import datetime, timedelta
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

    g = get_github_instance(pat_token, actions_token, app_id, app_installation_id, app_private_key)
    repo = g.get_repo(f"{owner}/{repo}")

    prs_response = get_pull_requests(repo, branch)
    pr_processing_result = process_pull_requests(prs_response, number_of_days, commit_counting_method)

    workflows_response = get_workflows(repo)
    workflow_processing_result = process_workflows(workflows_response, workflows_array, repo, branch, number_of_days)

    return evaluate_lead_time(pr_processing_result, workflow_processing_result, number_of_days)

def get_github_instance(pat_token, actions_token):
    if pat_token:
        return Github(pat_token)
    elif actions_token:
        return Github(actions_token)
    else:
        raise Exception("No valid authentication method provided.")

def get_pull_requests(repo, branch):
    return repo.get_pulls(state='closed', base=branch)

def process_pull_requests(prs, number_of_days, commit_counting_method):
    pr_counter = 0
    total_pr_hours = 0
    for pr in prs:
        merged_at = pr.merged_at
        if merged_at and merged_at > datetime.utcnow() - timedelta(days=number_of_days):
            pr_counter += 1
            commits = pr.get_commits()
            if commit_counting_method == "last":
                start_date = commits.reversed[0].commit.committer.date
            elif commit_counting_method == "first":
                start_date = commits[0].commit.committer.date
            duration = merged_at - start_date
            total_pr_hours += duration.total_seconds() / 3600
    return pr_counter, total_pr_hours

def get_workflows(repo):
    return repo.get_workflows()

def process_workflows(workflows, workflow_names, repo, branch, number_of_days):
    workflow_ids = [wf.id for wf in workflows if wf.name in workflow_names]
    total_workflow_hours = 0
    workflow_counter = 0
    for workflow_id in workflow_ids:
        runs = repo.get_workflow_runs(workflow_id=workflow_id, status='completed')
        for run in runs:
            if run.head_branch == branch and run.created_at > datetime.utcnow() - timedelta(days=number_of_days):
                workflow_counter += 1
                start_time = run.created_at
                end_time = run.updated_at
                duration = end_time - start_time
                total_workflow_hours += duration.total_seconds() / 3600
    return workflow_counter, total_workflow_hours

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
            "pr_average_time_duration": pr_average,
            "workflow_average_time_duration": workflow_average,
            "lead_time_for_changes_in_hours": lead_time_for_changes_in_hours
    }
    return json.dumps(report, default=str)
    
if __name__ == "__main__":
    owner_repo = os.getenv('REPOSITORY')
    token = os.getenv('GITHUB_TOKEN')  # Your personal access token or GitHub App token
    workflows = os.getenv('WORKFLOWS')
    branch = 'main'
    time_frame = int(os.getenv('TIMEFRAME_IN_DAYS'))
    number_of_days = 30 if not time_frame else time_frame
    
    report = main(owner_repo, workflows, branch, number_of_days, pat_token=token)
    with open(os.getenv('GITHUB_ENV'), 'a') as github_env:
        github_env.write(f"report={report}\n")
