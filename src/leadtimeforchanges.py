from github import Github
from datetime import datetime, timedelta
import os

class GithubLeadTimeCalculator:
    def __init__(self, token, owner_repo, workflows, branch, number_of_days, commit_counting_method="last"):
        self.github_client = Github(token)
        self.owner, self.repo_name = owner_repo.split('/')
        self.repo = self.github_client.get_repo(f"{self.owner}/{self.repo_name}")
        self.workflows = workflows.split(',')
        self.branch = branch
        self.number_of_days = number_of_days
        self.commit_counting_method = commit_counting_method if commit_counting_method else "last"

    def get_pull_requests(self):
        prs = self.repo.get_pulls(state='closed', base=self.branch)
        return [pr for pr in prs if pr.merged and pr.merged_at > datetime.utcnow() - timedelta(days=self.number_of_days)]

    def process_pull_requests(self, pull_requests):
        pr_counter = len(pull_requests)
        total_pr_hours = sum([(pr.merged_at - pr.get_commits()[0 if self.commit_counting_method == "first" else -1].commit.committer.date).total_seconds() / 3600 for pr in pull_requests])
        return pr_counter, total_pr_hours

    def get_workflows(self):
        return [wf for wf in self.repo.get_workflows() if wf.name in self.workflows]

    def process_workflows(self, workflows):
        workflow_counter = 0
        total_workflow_hours = 0
        for wf in workflows:
            runs = wf.get_runs(status='completed', branch=self.branch)
            valid_runs = [run for run in runs if run.created_at > datetime.utcnow() - timedelta(days=self.number_of_days)]
            workflow_counter += len(valid_runs)
            total_workflow_hours += sum([(run.updated_at - run.created_at).total_seconds() / 3600 for run in valid_runs])
        return workflow_counter, total_workflow_hours

    def evaluate_lead_time(self, pr_result, workflow_result):
        pr_counter, total_pr_hours = pr_result
        workflow_counter, total_workflow_hours = workflow_result
        pr_average = round(total_pr_hours / max(pr_counter, 1), 2)
        workflow_average = round(total_workflow_hours / max(workflow_counter, 1), 2)
        lead_time_for_changes_in_hours = round(pr_average + workflow_average, 2)
        return pr_average, workflow_average, lead_time_for_changes_in_hours

    def run(self):
        pull_requests = self.get_pull_requests()
        pr_result = self.process_pull_requests(pull_requests)
        workflows = self.get_workflows()
        workflow_result = self.process_workflows(workflows)
        pr_average, workflow_average, lead_time_for_changes = self.evaluate_lead_time(pr_result, workflow_result)
        print(f"PR average time duration: {pr_average} hours")
        print(f"Workflow average time duration: {workflow_average} hours")
        print(f"Lead time for changes in hours: {lead_time_for_changes}")
        
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

    calculator = GithubLeadTimeCalculator(token, owner_repo, workflows, branch, number_of_days)
    report = calculator.run()
    with open(os.getenv('GITHUB_ENV'), 'a') as github_env:
        github_env.write(f"report={report}\n")
