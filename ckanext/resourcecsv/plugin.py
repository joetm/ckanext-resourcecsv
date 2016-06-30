""" resourcecsv extension """

import ckan.plugins as p
import ckan.plugins.toolkit as tk

from ckan import model

import os
import inspect

import urllib2
import json

import tempfile

import ckanapi

from ckan.lib.munge import munge_filename

import pylons.config as pluginconf # to get the config setting for this plugin

import logging
log = logging.getLogger(__name__)



class ResourceCSVPlugin(p.SingletonPlugin):
    """
    Converts resources to CSV
    """

    DELIMITER = ';'


    p.implements(p.IConfigurer)
    def update_config(self, config):
    	# add the template dir
        tk.add_template_directory(config, 'templates')


    def _load_schema_module_path(self, url):
        """
        Given a path like "ckanext.resourcecsv:infoplus.json"
        find the second part relative to the import path of the first
        (taken from ckanext-scheming)
        """
        module, file_name = url.split(':', 1)
        try:
            m = __import__(module, fromlist=[''])
        except ImportError:
            return
        p = os.path.join(os.path.dirname(inspect.getfile(m)), file_name)
        if os.path.exists(p):
            return open(p)


    def check_and_create_csv(self, context, resource):

        log.debug("Resource: %s" % str(resource))

        resource_filename = os.path.basename(resource.get('url'))
        if not resource_filename:
            return
        log.debug('resource_filename: %s' % resource_filename)

        try:

            # get the config of this plugin
            infoplus_schema_file = pluginconf.get('ckanext.resourcecsv.schemas.infoplus', False)
            if not infoplus_schema_file:
                pass
            # log.debug('Infoplus_schema_file: %s' % str(infoplus_schema_file))
            infoplus_schema = json.load(self._load_schema_module_path(infoplus_schema_file))

        except Exception as e:
            log.error('ResourceCSV Plugin scheming error: %s' % str(e))
            return

        # log.debug('infoplus_schema: %s' % str(infoplus_schema))

        # check if the file is in the schema

        munged_filename = munge_filename(resource_filename)
        log.debug('munged_filename: %s' % munged_filename)
        coldef = []
        for key,cdef in infoplus_schema.iteritems():
            if munge_filename(key) != resource_filename:
                continue # skip
            coldef = cdef
            break

        if not len(coldef):
            log.info("Key %s not found in munged infoplus_schema" % str(munged_filename))
            return

        # download the file to a tmp location

        # with tempfile.NamedTemporaryFile(mode='ab+') as tmpfile:
        # tmpfile = tempfile.NamedTemporaryFile(mode='ab+')

        uploadfile = os.path.join('/tmp/', resource_filename) + '.csv'

        tmpfile = open(uploadfile, 'ab+')

        log.info("Downloading %s" % os.path.basename(resource.get('url')))

        data = urllib2.urlopen(resource.get('url')).readlines()

        # replace the defined characters in each line with a delimiter
        for line in data:

            # ignore any lines that start with a comment
            if line.startswith('#'):
                continue # skip
            if line.startswith('*'):
                continue # skip
            if line.startswith('%'):
                continue # skip

            tl = list(line) # explode

            # inject the delimiter
            for col in coldef:
                tl[col] = self.DELIMITER

            line = "".join(tl) # implode

            log.debug(line)

            tmpfile.write(line)

        # establish a connection to ckan
        try:
            site_url = pluginconf.get('ckan.site_url', None)
            api_key = model.User.get(context['user']).apikey.encode('utf8')
            ckan = ckanapi.RemoteCKAN(site_url,
                apikey=api_key,
                user_agent='ckanapi/1.0 (+%s)' % site_url
            )
            log.debug("Connected to %s" % site_url)
        except ckanapi.NotAuthorized, e:
            log.error('User not authorized')
            return False
        except ckanapi.CKANAPIError, e:
            log.error('Could not connect to CKAN via API')
            return False
        except ckanapi.ServerIncompatibleError, e:
            log.error('Could not connect to CKAN via API (remote API is not a CKAN API)')
            return False

        # reset the file pointer, or otherwise the upload will be empty
        tmpfile.seek(0)


        # TODO:

            # check if the csv version of this file already exists

            # the csv version exists: replace it

            # the csv version does not exist:


        # log.debug('rename tmp file: %s to %s' % (tmpfile.name, uploadfile))
        # os.rename(tmpfile.name, uploadfile)

        # upload the file into the dataset
        resource = ckan.action.resource_create(
            package_id=resource.get('package_id'),
            name=resource.get('name'),
            description=resource.get('description'),
            format='CSV',
            mimetype='CSV',
            mimetype_inner='CSV',
            url='dummy-value', # ignored, but required by ckan
            upload=tmpfile
        )

        tmpfile.close()


    p.implements(p.IResourceController, inherit=True)

    def after_create(self, context, resource):

        self.check_and_create_csv(context, resource)

    def after_update(self, context, resource):

        resource_url = resource.get('url')

        self.check_and_create_csv(context, resource)

    # TODO
    # def after_delete(context, resource):
    #     pass

