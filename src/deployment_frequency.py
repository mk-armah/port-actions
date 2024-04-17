import datetime
import os
import json
from github import Github
from loguru import logger


class DeploymentFrequency:
    def __init__(self, owner, repo, workflows, branch, number_of_days, pat_token=""):
        self.owner, self.repo = owner, repo
        self.workflows = json.loads(workflows)
        self.branch = branch
        self.number_of_days = number_of_days
        self.pat_token = pat_token
        self.github = Github(self.pat_token)
        self.repo_object = self.github.get_repo(f"{self.owner}/{self.repo}")

    def get_workflows(self):
        if not self.workflows:
            workflows = self.repo_object.get_workflows()
            workflow_ids = [workflow.id for workflow in workflows]
            logger.info(f"Found {len(workflow_ids)} workflows in Repo")
            return workflow_ids
        else:
            return self.workflows

    def fetch_workflow_runs(self):
        workflow_ids = self.get_workflows()
        workflow_runs_list = []
        unique_dates = set()
        for workflow_id in workflow_ids:
            for run in self.repo_object.get_workflow(workflow_id).get_runs():
                run_date = run.created_at.replace(tzinfo=None)
                if run.head_branch == self.branch and run_date > datetime.datetime.now() - datetime.timedelta(days=self.number_of_days):
                    workflow_runs_list.append(run)
                    unique_dates.add(run_date.date())
        return workflow_runs_list, unique_dates

    def calculate_deployments_per_day(self, workflow_runs_list):
        if self.number_of_days > 0:
            return len(workflow_runs_list) / self.number_of_days
        return 0

    def compute_rating(self, deployments_per_day):
        daily_deployment = 1
        weekly_deployment = 1 / 7
        monthly_deployment = 1 / 30
        yearly_deployment = 1 / 365

        if deployments_per_day > daily_deployment:
            return "Elite", "brightgreen"
        elif weekly_deployment <= deployments_per_day <= daily_deployment:
            return "High", "green"
        elif monthly_deployment <= deployments_per_day < weekly_deployment:
            return "Medium", "yellow"
        elif yearly_deployment < deployments_per_day < monthly_deployment:
            return "Low", "red"
        else:
            return "None", "lightgrey"

    def __call__(self):
        workflow_runs_list, unique_dates = self.fetch_workflow_runs()
        deployments_per_day = self.calculate_deployments_per_day(workflow_runs_list)
        rating, color = self.compute_rating(deployments_per_day)

        logger.info(f"Owner/Repo: {self.owner}/{self.repo}")
        logger.info(f"Workflows: {self.get_workflows()}")
        logger.info(f"Branch: {self.branch}")
        logger.info(f"Number of days: {self.number_of_days}")
        logger.info(f"Deployment frequency over the last {self.number_of_days} days is {deployments_per_day} per day")
        logger.info(f"Rating: {rating} ({color})")

        print("Unique Dates", unique_dates)
        return json.dumps({
            "deployment_frequency": round(deployments_per_day, 2),
            "rating": rating,
            "number_of_unique_deployment_days": len(unique_dates),
            "number_of_unique_deployment_weeks": len({date.isocalendar()[1] for date in unique_dates}),
            "number_of_unique_deployment_month": len({date.month for date in unique_dates}),
            "total_deployments": len(workflow_runs_list),
        }, default=str)


# if __name__ == "__main__":
#     owner = os.getenv("OWNER")
#     repo = os.getenv("REPOSITORY")
#     pat_token = os.getenv("GITHUB_TOKEN")
#     workflows = os.getenv("WORKFLOWS", "[]")
#     branch = os.getenv("BRANCH", "main")
#     time_frame = int(os.getenv("TIMEFRAME_IN_DAYS", 30))

#     deployment_frequency = DeploymentFrequency(owner, repo, workflows, branch, time_frame, pat_token)
#     report = deployment_frequency()

#     with open(os.getenv("GITHUB_ENV"), "a") as github_env:
#         github_env.write(f"deployment_frequency_report={report}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Calculate Deployment Frequency.')
    parser.add_argument('--owner', required=True, help='Owner of the repository')
    parser.add_argument('--repo', required=True, help='Repository name')
    parser.add_argument('--token', required=True, help='GitHub token')
    parser.add_argument('--branch', default='main', help='Branch name')
    parser.add_argument('--timeframe', type=int, default=30, help='Timeframe in days')
    parser.add_argument('--platform', default='github_actions', help = 'Platform where script is being run on')
    args = parser.parse_args()

    owner = args.owner
    repo = args.repo
    token = args.token
    branch = args.branch
    time_frame = args.timeframe

    lead_time_for_changes = LeadTimeForChanges(
        owner, repo, branch, time_frame, pat_token=token
    )
    report = lead_time_for_changes()
    print(report)
