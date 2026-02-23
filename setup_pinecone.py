#!/usr/bin/env python3
"""One-time setup script to create Pinecone index."""
import logging
import time

from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
import config

logger = logging.getLogger(__name__)

load_dotenv()


def main():
    logger.info("Connecting to Pinecone...")
    pc = Pinecone(api_key=config.PINECONE_API_KEY)

    index_name = config.PINECONE_INDEX_NAME

    existing_indexes = pc.list_indexes().names()

    if index_name in existing_indexes:
        # Check if dimension matches
        index = pc.Index(index_name)
        stats = index.describe_index_stats()

        if stats.dimension != config.EMBEDDING_DIM:
            logger.info("Index exists but has wrong dimension (%d vs %d)", stats.dimension, config.EMBEDDING_DIM)
            logger.info("Deleting index '%s'...", index_name)
            pc.delete_index(index_name)
            time.sleep(2)  # Wait for deletion
        else:
            logger.info("Index '%s' already exists with correct dimension.", index_name)
            logger.info("  Vectors: %d", stats.total_vector_count)
            return

    logger.info("Creating index '%s' with dimension %d...", index_name, config.EMBEDDING_DIM)
    pc.create_index(
        name=index_name,
        dimension=config.EMBEDDING_DIM,  # ECAPA-TDNN = 192
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

    # Wait for index to be ready
    logger.info("Waiting for index to be ready...")
    time.sleep(5)

    logger.info("Index '%s' created successfully!", index_name)
    logger.info("You can now run the app with: python app.py")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
