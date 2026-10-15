"""Remove the upstream launcher upgrade offer from the personal application."""


def configure_personal_distribution(config):
    # There is no published personal update repository yet. An official
    # launcher upgrade can restore upstream sources, so remove that offer too.
    config.pop('update_pyappify', None)
    config['version'] = str(config['version']) + '+personal.hdr1'
