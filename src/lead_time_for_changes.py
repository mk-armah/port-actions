import datetime
import os
import json
from github import Github
from loguru import logger

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
        self.workflows = json.loads(workflows)
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
        workflow_result = self.process_workflows()

        return self.evaluate_lead_time(pr_result, workflow_result)

    def get_pull_requests(self):
        return list(self.repo_object.get_pulls(state='closed', base=self.branch))

    def process_pull_requests(self):
        prs = self.get_pull_requests()
        pr_counter = 0
        total_pr_hours = 0
        for pr in prs:
            if pr.merged and pr.merge_commit_sha and pr.merged_at > datetime.datetime.now() - datetime.timedelta(days=self.number_of_days):
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
        if not self.workflows:
            workflows = list(self.repo_object.get_workflows())
            workflow_ids = [workflow.id for workflow in workflows]
            logger.info(f"Found {len(workflow_ids)} workflows in Repo")
            return workflow_ids
        else:
            return self.workflows

    def process_workflows(self):
        workflow_ids = self.get_workflows()
        total_workflow_hours = 0
        workflow_counter = 0
        for workflow_id in workflow_ids:
            runs = list(self.repo_object.get_workflow(workflow_id).get_runs())
            for run in runs:
                if run.head_branch == self.branch and run.created_at > datetime.datetime.now() - datetime.timedelta(days=self.number_of_days):
                    workflow_counter += 1
                    duration = run.updated_at - run.created_at
                    total_workflow_hours += duration.total_seconds() / 3600
        return workflow_counter, total_workflow_hours

    def calculate_rating(self, lead_time_for_changes_in_hours):
        # Logic remains the same as your original script
        ...

    def evaluate_lead_time(self, pr_result, workflow_result):
        # Logic remains the same as your original script
        ...


if __name__ == "__main__":
    owner = os.getenv("OWNER")
    repo = os.getenv("REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")
    workflows = os.getenv("WORKFLOWS", "[]")
    branch = os.getenv("BRANCH", "main")
    time_frame = int(os.getenv("TIMEFRAME_IN_DAYS", 30))

    lead_time_for_changes = LeadTimeForChanges(
        owner, repo, workflows, branch, time_frame, pat_token=token
    )
    report = lead_time_for_changes()
    with open(os.getenv("GITHUB_ENV"), "a") as github_env:
        github_env.write(f"lead_time_for_changes_report={report}\n")
