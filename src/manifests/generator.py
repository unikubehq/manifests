import logging
import uuid
from urllib.parse import urljoin

from commons.helm.context_manager import HelmCharts
from commons.helm.data_classes import AWSKMS, DeckData, PGPKey, RenderEnvironment, SopsProviderType
from commons.helm.parser import HelmRepositoryParser
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from sanic.request import Request
from sanic.response import BaseHTTPResponse, json, text

import settings

logger = logging.getLogger()


async def generate_manifests(request: Request, environment_id: str) -> BaseHTTPResponse:  # noqa
    try:
        environment_id = uuid.UUID(environment_id)
    except ValueError:
        # this is not a valid uuid
        return text("This environment is not a valid uuid.", status=400)

    transport = RequestsHTTPTransport(
        url=urljoin(settings.PROJECTS_SVC, "/graphql"),
        headers={"x-internal": "manifests", "x-forwarded-access-token": request.headers["x-forwarded-access-token"]},
    )
    client = Client(transport=transport, fetch_schema_from_transport=False)

    query = gql(
        """
    query($environment: UUID!)
    {
      environment(id: $environment){
        id
        namespace
        deck {
          hash
          project {
            specRepository
            specRepositoryBranch
            accessToken
            accessUsername
            specType
          }
        }
        sopsCredentials {
          __typename
          ...on AWSKMSNode {
            title
            accessKey
            secretAccessKey
          }
          ...on PGPKeyNode {
            privateKey
          }
        }
        valuesPath
        helmOverrides {
          overrides
        }
      }
    }
    """
    )
    # this is ensured to be a UUID
    params = {"environment": str(environment_id)}
    try:
        result = client.execute(query, variable_values=params)
    except Exception as e:
        # we cannot retrieve this environment from project service
        logger.debug(e)
        return text("This environment cannot be retrieved.", status=404)

    environment = result["environment"]
    project = environment["deck"]["project"]
    if project["specType"] == "HELM":
        parser = HelmRepositoryParser(
            repository_url=project["specRepository"],
            access_username=project["accessUsername"],
            access_token=project["accessToken"],
            branch=project["specRepositoryBranch"],
        )
        parser.parse()
        decks = parser.get_deck_data()
        # get the deck in question from the repo
        deck = next(x for x in decks if x.hash == environment["deck"]["hash"])
        deck.namespace = environment["namespace"]
        if environment.get("sopsCredentials"):
            sops = environment.get("sopsCredentials")
            if sops["__typename"] == "AWSKMSNode":
                logger.info("Running generator with AWSKMS")
                deck.sops = AWSKMS(
                    access_key=environment["sopsCredentials"]["accessKey"],
                    secret_access_key=environment["sopsCredentials"]["secretAccessKey"],
                    type=SopsProviderType.AWS,
                )
            elif sops["__typename"] == "PGPKeyNode":
                logger.info("Running generator with PGP")
                pkey = environment["sopsCredentials"]["privateKey"]
                deck.sops = PGPKey(
                    # todo this is a workaround, fix
                    private_key=" ".join(pkey.split(" ")[:5])
                    + "\n"
                    + "\n".join(pkey.split(" ")[5:-5])
                    + "\n"
                    + " ".join(pkey.split(" ")[-5:]),
                    type=SopsProviderType.PGP,
                )

        render_environment = RenderEnvironment(values_path=environment["valuesPath"], specs_data=[])
        if environment["helmOverrides"] and environment["helmOverrides"]["overrides"]:
            render_environment.update_values_from_yaml(environment["helmOverrides"]["overrides"])
        result = parser.render((deck, render_environment))

        _, updated_environment = result[0]
        return json(
            [
                {"name": file.name, "source": file.source, "content": file.content}
                for file in updated_environment.specs_data
            ]
        )

    else:
        raise text(f"A project with spec_type {project['specType']} is not supported.", status=500)
