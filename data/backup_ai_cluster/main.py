"""CLI entrypoint for Contract A to Contract B workflow discovery."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from ai_cluster.config.settings import settings
from ai_cluster.prompts.workflow_prompt import WorkflowPromptBuilder
from ai_cluster.services.clustering_service import WorkflowClusteringService
from ai_cluster.services.ollama_service import OllamaService, OllamaServiceError
from ai_cluster.services.validation_service import (
    WorkflowValidationError,
    WorkflowValidationService,
)
from ai_cluster.utils.file_handler import FileHandler
from ai_cluster.utils.logger import configure_logging


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for workflow discovery."""
    parser = argparse.ArgumentParser(
        description="Generate Contract B workflow_mapping.json from Contract A."
    )
    parser.add_argument(
        "contract_a",
        type=Path,
        help="Path to Contract A JSON produced by Person 2.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.OUTPUT_PATH,
        help="Path where Contract B workflow_mapping.json should be written.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the local workflow discovery pipeline."""
    configure_logging()
    logger = logging.getLogger(__name__)
    args = parse_args()

    file_handler = FileHandler()
    validation_service = WorkflowValidationService()

    try:
        contract_a_payload = file_handler.read_json(args.contract_a)
        endpoints = validation_service.validate_contract_a(contract_a_payload)
        logger.info("Loaded %s APIs", len(endpoints))

        clustering_service = WorkflowClusteringService(
            ollama_service=OllamaService(logger=logger),
            validation_service=validation_service,
            prompt_builder=WorkflowPromptBuilder(),
            logger=logger,
        )
        mapping = clustering_service.generate(endpoints)
        file_handler.write_json(args.output, mapping.model_dump(mode="json"))
        logger.info("Wrote workflow mapping to %s", args.output)
        return 0
    except FileNotFoundError as exc:
        logger.error("%s", exc)
    except ValueError as exc:
        logger.error("Validation failed: %s", exc)
    except WorkflowValidationError as exc:
        logger.error("Validation failed: %s", exc)
    except OllamaServiceError as exc:
        logger.error("%s", exc)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
