import kopf

from gefyra.purge import purge_operator


@kopf.on.cleanup()
def remove_everything(logger, **kwargs):
    logger.info("Operator shutdown requested")
    try:
        purge_operator()
    except Exception as e:
        logger.exception(e)
