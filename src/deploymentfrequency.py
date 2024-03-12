from github import Github
from datetime import datetime, timedelta

class GitHubRepo:
    def __init__(self, owner_repo, token):
        self.owner, self.repo_name = owner_repo.split('/')
        self.github = Github(token)
        self.repo = self.github.get_repo(f"{self.owner}/{self.repo_name}")

    def get_workflows(self, workflow_names):
        workflows = self.repo.get_workflows()
        return [wf for wf in workflows if wf.name in workflow_names]

class Workflow:
    def __init__(self, workflow, branch, start_date, end_date):
        self.workflow = workflow
        self.branch = branch
        self.start_date = start_date
        self.end_date = end_date

    def get_successful_runs(self):
        successful_runs = []
        for run in self.workflow.get_runs():
            run_date = run.created_at.replace(tzinfo=None)  # Remove timezone for comparison
            if run.head_branch == self.branch and self.start_date <= run_date <= self.end_date and run.conclusion == 'success':
                successful_runs.append(run_date.date())
        return successful_runs

class DeploymentFrequencyCalculator:
    def __init__(self, owner_repo, token, workflows, branch, number_of_days):
        self.repo = GitHubRepo(owner_repo, token)
        self.workflows = workflows.split(',')
        self.branch = branch
        self.number_of_days = number_of_days
        self.end_date = datetime.utcnow()
        self.start_date = self.end_date - timedelta(days=number_of_days)

    def calculate_deployment_frequency(self):
        unique_dates = set()
        for workflow_name in self.workflows:
            for wf in self.repo.get_workflows(self.workflows):
                if wf.name == workflow_name:
                    workflow = Workflow(wf, self.branch, self.start_date, self.end_date)
                    unique_dates.update(workflow.get_successful_runs())

        unique_deployments = len(unique_dates)
        frequency_per_day = unique_deployments / self.number_of_days if self.number_of_days > 0 else 0
        return frequency_per_day, unique_deployments, self._calculate_rating(frequency_per_day)

    def _calculate_rating(self, frequency_per_day):
        if frequency_per_day > 1:
            return "Elite"
        elif frequency_per_day >= 1/7:
            return "High"
        elif frequency_per_day >= 1/30:
            return "Medium"
        elif frequency_per_day > 1/365:
            return "Low"
        else:
            return "None"

def main():
    # Parameters
    owner_repo = 'owner/repo'
    token = ''  # Your personal access token or GitHub App token
    workflows = 'workflow1,workflow2'
    branch = 'main'
    number_of_days = 30

    calculator = DeploymentFrequencyCalculator(owner_repo, token, workflows, branch, number_of_days)
    frequency_per_day, unique_deployments, rating = calculator.calculate_deployment_frequency()

    print(f"Deployment frequency: {frequency_per_day:.2f} per day")
    print(f"DORA rating: {rating}")
    print(f"Number of unique deployment days: {unique_deployments}")

if __name__ == "__main__":
    main()
