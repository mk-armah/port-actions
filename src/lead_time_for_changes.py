import datetime
import os
import json
from github import Github
from loguru import logger
import argparse

class LeadTimeForChanges:
    def __init__(
        self,
        owner,
        repo,
        workflows,
        branch,
        number_of_days,
        commit_counting_method="last",
        pat_token="",
    ):
        self.owner = owner
        self.repo = repo
        self.workflows = json.loads(workflows) if workflows else None
        self.branch = branch
        self.number_of_days = number_of_days
        self.commit_counting_method = commit_counting_method
        self.github = Github(pat_token)
        self.repo_object = self.github.get_repo(f"{self.owner}/{self.repo}")

    def __call__(self):
        logger.info(f"Owner/Repo: {self.owner}/{self.repo}")
        logger.info(f"Number of days: {self.number_of_days}")
        logger.info(f"Workflows: {self.get_workflows()}")
        logger.info(f"Branch: {self.branch}")
        logger.info(f"Commit counting method '{self.commit_counting_method}' being used")

        pr_result = self.process_pull_requests()
        workflow_result = self.process_workflows() if self.workflows != None else None

        return self.evaluate_lead_time(pr_result, workflow_result)

    def get_pull_requests(self):
        return list(self.repo_object.get_pulls(state='closed', base=self.branch))

    def process_pull_requests(self):
        prs = self.get_pull_requests()
        pr_counter = 0
        total_pr_hours = 0
        # Ensure now is also offset-aware by using UTC
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        for pr in prs:
            if pr.merged and pr.merge_commit_sha and pr.merged_at > now_utc - datetime.timedelta(days=self.number_of_days):
                pr_counter += 1
                commits = list(pr.get_commits())
                if commits:
                    if self.commit_counting_method == "last":
                        start_date = commits[-1].commit.committer.date
                    elif self.commit_counting_method == "first":
                        start_date = commits[0].commit.committer.date
                    merged_at = pr.merged_at
                    duration = merged_at - start_date
                    total_pr_hours += duration.total_seconds() / 3600
        return pr_counter, total_pr_hours

    def get_workflows(self):
        if self.workflows==[]:
            workflows = list(self.repo_object.get_workflows())
            workflow_ids = [workflow.id for workflow in workflows]
            logger.info(f"Found {len(workflow_ids)} workflows in Repo")
            return workflow_ids
        else:
            return self.workflows

    def process_pull_requests(self):
        prs = self.get_pull_requests()
        pr_counter = 0
        total_pr_hours = 0
        # Ensure now is also offset-aware by using UTC
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        for pr in prs:
            if pr.merged and pr.merge_commit_sha and pr.merged_at > now_utc - datetime.timedelta(days=self.number_of_days):
                pr_counter += 1
                commits = list(pr.get_commits())
                if commits:
                    if self.commit_counting_method == "last":
                        start_date = commits[-1].commit.committer.date
                    elif self.commit_counting_method == "first":
                        start_date = commits[0].commit.committer.date
                    merged_at = pr.merged_at
                    duration = merged_at - start_date
                    total_pr_hours += duration.total_seconds() / 3600
        return pr_counter, total_pr_hours

    def calculate_rating(self, lead_time_for_changes_in_hours):
        daily_deployment = 24
        weekly_deployment = 24 * 7
        monthly_deployment = 24 * 30
        every_six_months_deployment = 24 * 30 * 6

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
        elif (
            monthly_deployment
            < lead_time_for_changes_in_hours
            <= every_six_months_deployment
        ):
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
            "display_unit": display_unit,
        }


    def evaluate_lead_time(self, pr_result, workflow_result):
        pr_counter, total_pr_hours = pr_result
        if pr_counter == 0:
            pr_counter = 1
        pr_average = total_pr_hours / pr_counter 

        if workflow_result:
            workflow_counter, total_workflow_hours = workflow_result
            if workflow_counter == 0:
                workflow_counter = 1
    
            workflow_average = total_workflow_hours / workflow_counter

        else:
            workflow_average = 0
            logger.info("Excluded workflows in computing metric")
            
        lead_time_for_changes_in_hours = pr_average + workflow_average
        logger.info(f"PR average time duration: {pr_average} hours")
        logger.info(f"Workflow average time duration: {workflow_average} hours")
        logger.info(f"Lead time for changes in hours: {lead_time_for_changes_in_hours}")

        report = {
            "pr_average_time_duration": round(pr_average, 2),
            "workflow_average_time_duration": round(workflow_average, 2),
            "lead_time_for_changes_in_hours": round(lead_time_for_changes_in_hours, 2),
        }
        rating = self.calculate_rating(lead_time_for_changes_in_hours)
        report.update(rating)

        return json.dumps(report, default=str)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Calculate lead time for changes.')
    parser.add_argument('--owner', required=True, help='Owner of the repository')
    parser.add_argument('--repo', required=True, help='Repository name')
    parser.add_argument('--token', required=True, help='GitHub token')
    parser.add_argument('--workflows', required=False, default = None, help='Github workflows')
    parser.add_argument('--branch', default='main', help='Branch name')
    parser.add_argument('--timeframe', type=int, default=30, help='Timeframe in days')
    parser.add_argument('--platform', default='github-actions', choices=['github-actions', 'self-hosted'], help='CI/CD platform type')
    args = parser.parse_args()

    lead_time_for_changes = LeadTimeForChanges(
        args.owner, args.repo, args.workflows, args.branch, args.timeframe, pat_token=args.token
    )
    report = lead_time_for_changes()
    print(report)
    
    if args.platform == "github-actions":
       with open(os.getenv("GITHUB_ENV"), "a") as github_env:
           github_env.write(f"lead_time_for_changes_report={report}\n")
