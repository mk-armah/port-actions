from github import Github
import datetime
import os

class GitHubAnalytics:
    def __init__(self, owner_repo, workflows, branch, number_of_days, commit_counting_method, token=None):
        self.owner, self.repo_name = owner_repo.split('/')
        self.workflows = workflows.split(',')  # Assuming workflows is a comma-separated string
        self.branch = branch
        self.number_of_days = number_of_days
        self.commit_counting_method = commit_counting_method
        self.github = Github(token) if token else Github()
        self.repo = self.github.get_repo(f"{self.owner}/{self.repo_name}")

    def calculate_lead_times(self):
        pr_lead_times = self._calculate_pr_lead_times()
        workflow_lead_times = self._calculate_workflow_lead_times()

        average_pr_time = sum(pr_lead_times) / len(pr_lead_times) if pr_lead_times else 0
        average_workflow_time = sum(workflow_lead_times) / len(workflow_lead_times) if workflow_lead_times else 0
        return average_pr_time, average_workflow_time

    def _calculate_pr_lead_times(self):
        start_date = datetime.datetime.now() - datetime.timedelta(days=self.number_of_days)
        prs = self.repo.get_pulls(state='closed', base=self.branch, sort='created', direction='desc')
        lead_times = []

        for pr in prs:
            if pr.merged and pr.merged_at > start_date:
                commits = pr.get_commits()
                first_commit_date = commits[0].commit.committer.date if self.commit_counting_method == 'first' else commits[-1].commit.committer.date
                pr_duration = (pr.merged_at - first_commit_date).total_seconds() / 3600.0  # Convert to hours
                lead_times.append(pr_duration)
        
        return lead_times

    def _calculate_workflow_lead_times(self):
        start_date = datetime.datetime.now() - datetime.timedelta(days=self.number_of_days)
        workflows = self.repo.get_workflows()
        lead_times = []

        for workflow in workflows:
            if workflow.name in self.workflows:
                runs = workflow.get_runs(branch=self.branch)
                for run in runs:
                    if run.status == "completed" and run.created_at > start_date:
                        duration = (run.updated_at - run.created_at).total_seconds() / 3600.0  # Convert to hours
                        lead_times.append(duration)

        return lead_times

    def display_results(self, average_pr_time, average_workflow_time):
        print(f"PR average time duration: {average_pr_time} hours")
        print(f"Workflow average time duration: {average_workflow_time} hours")
        # Add more detailed results or formatting here as needed

# Usage
if __name__ == "__main__":
    owner_repo = "owner/repo"  # Format: "owner/repo"
    workflows = "workflow1,workflow2"  # Comma-separated workflow names
    branch = "main"
    number_of_days = 30
    commit_counting_method = "last"  # "last" or "first"
    token = "your_token_here"  # Replace with your actual token or None for unauthenticated access

    analytics = GitHubAnalytics(owner_repo, workflows, branch, number_of_days, commit_counting_method, token)
    average_pr_time, average_workflow_time = analytics.calculate_lead_times()
    analytics.display_results(average_pr_time, average_workflow_time)
    
