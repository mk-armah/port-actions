import os
import asyncio
from github import Github, Team, PullRequest, GithubException
import datetime
import json
import logging
import argparse
import re
from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Any, Dict, List, Tuple
from port import PortAPI

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class TeamMetrics:
    def __init__(
        self, owner: str, time_frame: int, token: str, base_url: str | None
    ) -> None:
        try:
            self.github_client = (
                Github(login_or_token=token, base_url=base_url)
                if base_url
                else Github(token)
            )
            self.owner = owner
        except GithubException as e:
            logging.error(f"Failed to initialize GitHub client: {e}")
            raise
        except Exception as e:
            logging.error(
                f"Unexpected error during initialization: {e} - verify that your github credentials are valid"
            )
            raise

        self.time_frame = time_frame
        self.start_date = datetime.datetime.now(
            datetime.timezone.utc
        ) - datetime.timedelta(days=self.time_frame)
        self.semaphore = threading.Semaphore(5)  # Limit concurrent requests

    @staticmethod
    def convert_to_slug(name: str) -> str:
        """Convert a team name to a slug by replacing spaces with hyphens and lowercasing."""
        return re.sub(r"\s+", "-", name.strip()).lower()

    async def get_teams(self) -> List[Team.Team]:
        try:
            logging.info(f"Fetching teams for organization {self.owner}")
            org = self.github_client.get_organization(self.owner)
            teams = org.get_teams()
            return [team for team in teams]
        except GithubException as e:
            logging.error(f"Failed to fetch teams: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error while fetching teams: {e}")
            raise

    def get_team_members(self, team: Team.Team) -> List[str]:
        try:
            logging.info(f"Fetching team members for team {team.slug}")
            return [member.login for member in team.get_members()]
        except GithubException as e:
            logging.error(f"Failed to fetch team members for team {team.slug}: {e}")
            raise
        except Exception as e:
            logging.error(
                f"Unexpected error while fetching team members for team {team.slug}: {e}"
            )
            raise

    def get_team_repositories(self, team: Team.Team) -> List[str]:
        try:
            logging.info(f"Fetching repositories for team {team.slug}")
            return [repo.full_name for repo in team.get_repos()]
        except GithubException as e:
            logging.error(f"Failed to fetch repositories for team {team.slug}: {e}")
            raise
        except Exception as e:
            logging.error(
                f"Unexpected error while fetching repositories for team {team.slug}: {e}"
            )
            raise

    async def calculate_response_metrics(
        self,
        prs: List[PullRequest.PullRequest],
        team_members: List[str],
        team_slug: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        logging.info(f"Calculating response rate and time for team {team_slug}")
        total_requests = 0
        responded_requests = 0
        total_response_time = datetime.timedelta(0)
        total_responses = 0

        def fetch_reviews(pr: PullRequest.PullRequest) -> None:
            nonlocal responded_requests, total_response_time, total_responses, total_requests
            try:
                with self.semaphore:  # Ensure limited concurrent requests
                    if any(team.slug == team_slug for team in pr.requested_teams):
                        total_requests += 1
                        reviews = pr.get_reviews()
                        for review in reviews:
                            if review.user.login in team_members:
                                responded_requests += 1
                                response_time = review.submitted_at - pr.created_at
                                total_response_time += response_time
                                total_responses += 1
                                break
            except GithubException as e:
                logging.error(f"Failed to fetch reviews for PR {pr.number}: {e}")
            except Exception as e:
                logging.error(
                    f"Unexpected error while fetching reviews for PR {pr.number}: {e}"
                )

        with ThreadPoolExecutor(max_workers=10) as executor:
            loop = asyncio.get_event_loop()
            futures = [loop.run_in_executor(executor, fetch_reviews, pr) for pr in prs]
            for future in asyncio.as_completed(futures):
                await future

        response_rate = (
            (responded_requests / total_requests) * 100 if total_requests else 0
        )
        average_response_time = (
            self.timedelta_to_decimal_hours(total_response_time / total_responses)
            if total_responses
            else 0
        )

        logging.info(
            f"Successfully retrieved team response metrics for team {team_slug}"
        )
        return {"response_rate": round(response_rate, 2)}, {
            "average_response_time": average_response_time
        }

    @staticmethod
    def timedelta_to_decimal_hours(td: datetime.timedelta) -> float:
        return round(td.total_seconds() / 3600, 2)

    async def calculate_metrics_for_team(self, team: Team.Team) -> Dict[str, Any]:
        all_prs = []
        try:
            team_members = self.get_team_members(team)
            repos = self.get_team_repositories(team)
            logging.info(f"Found {len(repos)} repositories for the team {team.slug}")

            for repo_name in repos:
                repo = self.github_client.get_repo(repo_name)
                prs = repo.get_pulls(state="all", sort="created", direction="desc")
                filtered_prs = [pr for pr in prs if pr.created_at >= self.start_date]
                all_prs.extend(filtered_prs)
                logging.info(
                    f"Fetched {len(filtered_prs)} pull requests from {repo_name}"
                )

            response_rate, response_time = await self.calculate_response_metrics(
                all_prs, team_members, team.slug
            )
            team_info = self.get_team_info(team)
            return {**response_rate, **response_time, **team_info, "time_frame": self.time_frame}
        except GithubException as e:
            logging.error(f"Failed to calculate metrics for team {team.slug}: {e}")
            raise
        except Exception as e:
            logging.error(
                f"Unexpected error while calculating metrics for team {team.slug}: {e}"
            )
            raise

    def get_team_info(self, team: Team.Team) -> Dict[str, Any]:
        try:
            logging.info(
                f"Fetching team info from {self.owner} organization for team {team.slug}"
            )
            return {
                "id": team.id,
                "name": team.name,
                "description": team.description,
                "members_count": team.members_count,
                "repos_count": team.repos_count,
                "slug": team.slug,
                "link": team.html_url,
                "permission": team.permission,
                "notification_setting": team.notification_setting,
            }
        except GithubException as e:
            logging.error(f"Failed to fetch team info for team {team.slug}: {e}")
            raise
        except Exception as e:
            logging.error(
                f"Unexpected error while fetching team info for team {team.slug}: {e}"
            )
            raise

    async def calculate_metrics_for_all_teams(self) -> List[Dict[str, Any]]:
        try:
            teams = await self.get_teams()
            tasks = [self.calculate_metrics_for_team(team) for team in teams]
            return await asyncio.gather(*tasks)
        except Exception as e:
            logging.error(f"Failed to calculate metrics for all teams: {e}")
            raise


class TeamEntityProcessor:
    def __init__(self, port_api: PortAPI) -> None:
        self.port_api = port_api

    @staticmethod
    def remove_symbols_and_title_case(input_string: str) -> str:
        cleaned_string = re.sub(r"[^A-Za-z0-9\s]", " ", input_string)
        title_case_string = cleaned_string.title()
        return title_case_string

    async def process_team_entities(self, team_dora: List[Dict[str, Any]]):
        blueprint_id = "githubTeam"
        tasks = [
            self.port_api.add_entity(
                blueprint_id=blueprint_id,
                entity_object={
                    "identifier": str(data["id"]),
                    "title": self.remove_symbols_and_title_case(data["name"]),
                    "properties": {
                        "description": data["description"],
                        "members_count": data["members_count"],
                        "repos_count": data["repos_count"],
                        "slug": data["slug"],
                        "link": data["link"],
                        "permission": data["permission"],
                        "notificationSetting": data["notification_setting"],
                        "responseRate": data["response_rate"],
                        "averageResponseTime": data["average_response_time"],
                        "timeFrame": data["time_frame"]
                    },
                    "relations": {},
                },
            )
            for data in team_dora
        ]
        await asyncio.gather(*tasks)


if __name__ == "__main__":

    try:
        parser = argparse.ArgumentParser(description="Calculate Team Metrics.")
        parser.add_argument("--owner", required=True, help="Owner of the organization")
        parser.add_argument("--token", required=True, help="GitHub token")
        parser.add_argument("--time-frame", type=int, default=30, help="Time Frame in days")
        parser.add_argument(
            "--base-url",
            help="Base URL for self-hosted GitHub instance (e.g., https://github.example.com/api/v3)",
            default=None,
        )
        parser.add_argument("--port-client-id", help="Port Client ID", required=True)
        parser.add_argument(
            "--port-client-secret", help="Port Client Secret", required=True
        )
        args = parser.parse_args()

        logging.info(f"Owner: {args.owner}")
        logging.info(f"Time Frame (in days): {args.time_frame}")

        team_metrics = TeamMetrics(
            args.owner, args.time_frame, token=args.token, base_url=args.base_url
        )

        loop = asyncio.get_event_loop()
        metrics = loop.run_until_complete(team_metrics.calculate_metrics_for_all_teams())
        port_api = PortAPI(args.port_client_id, args.port_client_secret)
        processor = TeamEntityProcessor(port_api=port_api)
        asyncio.run(processor.process_team_entities(metrics))
        
    except Exception as e:
        logging.error(f"Failed to execute script: {e}")
        raise
