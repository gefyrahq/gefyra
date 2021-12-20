from operator.purge import purge_operator

import kopf


@kopf.on.cleanup()
def remove_everything(logger, **kwargs):
    logger.info("Operator shutdown requested")
    try:
        purge_operator()
    except Exception as e:
        logger.exception(e)
