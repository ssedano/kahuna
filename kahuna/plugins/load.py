#!/usr/bin/env jython

from __future__ import with_statement  # jython 2.5.2 issue
import logging
import os
import atexit
from java.io import File
from kahuna.abstract import AbsPlugin
from kahuna.config import ConfigLoader
from kahuna.utils.prettyprint import pprint_templates
from com.google.common.collect import Iterables
from optparse import OptionParser
from org.jclouds.abiquo.domain.exception import AbiquoException
from org.jclouds.compute import RunNodesException
from org.jclouds.domain import LoginCredentials
from org.jclouds.io import Payloads
from org.jclouds.rest import AuthorizationException
from org.jclouds.util import Strings2
from org.jclouds.abiquo.predicates.infrastructure  import DatacenterPredicates, RackPredicates
from org.jclouds.abiquo.domain.infrastructure import Datacenter
from com.abiquo.model.enumerator import HypervisorType 
from org.jclouds.abiquo.domain.enterprise import Enterprise, User
from org.jclouds.abiquo.predicates.enterprise  import RolePredicates
from org.jclouds.abiquo.domain.cloud import VirtualDatacenter, VirtualAppliance, VirtualMachine
from org.jclouds.abiquo.domain.network import PrivateNetwork
from org.jclouds.abiquo.predicates.cloud import VirtualMachineTemplatePredicates
import random
from config import Config
from java.util import Properties
from org.jclouds import ContextBuilder
from org.jclouds.abiquo import AbiquoContext, AbiquoApiMetadata
from org.jclouds.logging.config import NullLoggingModule
from org.jclouds.ssh.jsch.config import JschSshClientModule
import time
from com.abiquo.server.core.cloud import  VirtualMachineState, VirtualApplianceState
import urllib2, base64
log = logging.getLogger('kahuna')


class LoadPlugin(AbsPlugin):
    """Env load plugin"""
    def __init__(self):
        self.__config = ConfigLoader().load("load.conf", "config/load.conf")
        self.u = {}

    def __del__(self):
        """ Closes the context before destroying """
        if self._context:
            log.debug("Disconnecting from %s" % self._context. \
                    getApiContext().getEndpoint())
            self._context.close()

    def iterate(self, args):
        """Iterates the loading"""
        aa = self.add()
        self.load(aa)

    
    def add(self):
        dc = self.add_infrastructure()
            
        e = self.add_enterprise(dc)
        self.refresh(e, dc)
        vdc = self.add_vdc(dc, e)
        users = self.add_users(e)
        aa = self.create_vapps(vdc, users)
        
        return aa

    def iterations(self, args):
        if len(args) < 1:
            raise "Invalid number of arguments: expected one numeric arguments (loop delay)"
        delay = args[0]
        log.info("applying delay %s" % delay)

        iterations = 1
        if len(args) == 2:
            iterations = args[1]
        log.info("iterations %s" % iterations)
        i = 1

        go = True
        while go:
            try:
                log.info("iteration %s" % i)
                self.add()
                time.sleep(float(delay))
            except (AbiquoException, AuthorizationException), e:
                log.info("%s" % e.getMessage()) 
            try:
                n = 0
                while ( n < iterations):
                    log.info("iteration %s out of %s, global %s" % (n, iterations, i))
                    self.load_all()
        
                    
                    n = n + 1
                    time.sleep(float(delay))
            except (AbiquoException, AuthorizationException), e:
                log.info("%s" % e.getMessage())
 
            i += 1 

    def add_infrastructure(self):
        """Adds machines"""
        log.info("### Configuring infrastructure ###")
        dc = self._context.getAdministrationService().findDatacenter(DatacenterPredicates.name("DC"))
        rack = dc.findRack(RackPredicates.name("rack"))

        sections = filter(lambda s: s.startswith("machine"), self.__config.sections())
        for section in sections:
            m = dc.discoverSingleMachine(self.__config.get(section, "address"),
                    HypervisorType.valueOf(self.__config.get(section, "type")),
                                        self.__config.get(section, "user"),
                    self.__config.get(section, "password"))

            d = m.findDatastore(self.__config.get(section, "datastore"))
            d.setEnabled(True)

            s = m.findAvailableVirtualSwitch(self.__config.get(section, "vswitch"))
            m.setVirtualSwitch(s)

            m.setRack(rack)
            m.save()
        return dc

    def add_enterprise(self, dc):
        """Adds an Enterprise"""
        log.info("### Adding Enterprise ###")
        e = None 
        sections = filter(lambda s: s.startswith("enterprise"), self.__config.sections())
        for section in sections:
            enterprise = Enterprise.builder(self._context.getApiContext()).name(self.__config.get(section, "name").join(str(random.randint(1, 441000))).strip()).cpuCountLimits(4, 0).ramLimits(0, 0).publicIpsLimits(0, 0).storageLimits(0, 0).build()

            enterprise.save()

            enterprise.allowDatacenter(dc)
            log.info("Allowed datacenter %s to enterprise %s..." % (dc.name,
                    self.__config.get(section, "name" )))
            e = enterprise
        return e

    def add_vdc(self, dc, e):
        log.info("### Creating a VDC ###")
       
        name = "e".join(str(random.randint(0, 100000000)))
        suffix = str(random.randint(0, 254))
        address = "192.168." + suffix
        
        
        network = PrivateNetwork.builder(self._context.getApiContext()) \
                  .name(name.join("net")) \
                  .address(address + ".0") \
                  .mask(24) \
                  .gateway(address + ".1") \
                  .build()
    
        vdc = VirtualDatacenter \
              .builder(self._context.getApiContext(), dc, e) \
              .name(name) \
              .hypervisorType(HypervisorType.VBOX) \
              .network(network) \
              .build()
        vdc.save()
        return vdc

        
    def add_users(self, enterprise):
        """logs in as a user to create users"""
        log.info("### Adding users ###")
        sections = filter(lambda s: s.startswith("user"), self.__config.sections())

        users = []
        for section in sections:
            for  i in range (0, 16):
                name = self.__config.get(section, "name")
                role = self.__config.get(section, "role")
                email = self.__config.get(section, "email")
                nick = self.__config.get(section, "login")
                password = self.__config.get(section, "password")

                log.info("Adding user %s as %s" % (name, role))

                admin = self._context.getAdministrationService()
                role = admin.findRole(RolePredicates.name(role))

                user = User.builder(self._context.getApiContext(),
                        enterprise, role) \
                       .name(name, name) \
                       .email(str(random.randint(0, 100000)) + email) \
                       .nick(nick + str(random.randint(0, 100000))) \
                       .password(password) \
                       .build()

                user.save()
                users.append(user)
        return users
            #print i

    def create_vapps(self, vdc, users):
        """All users create vapps"""

        a = []
        for user in users:
            context = self.create_context_user(user)            
            vapp = VirtualAppliance.builder(context.getApiContext(), vdc) \
               .name(user.getNick().join("APP")) \
               .build()
            vapp.save()
           
            self.create_vms( vdc, vapp, context)
            a.append(vapp)
            self.u[user.getNick()] = vapp
        return a


    def create_vms(self, vdc, app, context):
        """All users create vm"""
        vms = []
        for i in range(0, random.randint(1, 3)):
            template = self.find_template_by_type(vdc, HypervisorType.VBOX)
            vm = VirtualMachine.builder(context.getApiContext(), app, template).build()
            vm.save()
            vms.append(vm)

        return vms


    def find_template_by_type(self, vdc, hypervisorType):
        """ Finds the template with the given name """
        templates = vdc.listAvailableTemplates(
                VirtualMachineTemplatePredicates.compatible(hypervisorType))
        template = None
        if templates:
            template = random.choice(templates)
            log.info("Found compatible template: %s" % template.getName())
        else:
            log.info("No compatible template found")
        return template


    def load(self, vapps):
        """All users undeploy or deploy or reconfigure or query stat."""
        for a in vapps:
           log.info("vapp %s" %  a.name)
           n = random.randint(1, 7)
           log.info("%s" % n)
           if n <= 4: 
               self.undeploy_deploy_vapp(a)

        log.info("done") 

    def load_all(self):
        """ Iterate all """
        log.info("total %s" % len(self.u.keys()))
        for n, a in self.u.iteritems():
            context = self.create_context_user_nick(n)
            log.info("vapp %s in state %s" % (a.name, a.getState()))
            r = random.randint(1, 7)
            if r <= 4:
                self.action( a)
                self.query_stats(n)
        log.info("done")

    def refresh(self, enterprise, datacenter):
        """ Refresh the virtual machines templates in the given repository """
        log.info("Refreshing template repository...")
        enterprise.refreshTemplateRepository(datacenter)

    def undeploy_deploy_vapp(self, vapp):
        """ Deploy whole """
        vapp.deploy()
        
    def undeploy_deploy_vm(self, vm):
        """ Deploy """
        vm.deploy()

    def reconfigure(self, vm):
        """ """
        r = random.randint(1, 7)
        if r == 1:
            vm.setCpu(vm.getCpu() + 1)
        elif r == 2 and vm.getCpu() > 0:
            vm.setCpu(vm.getCpu() - 1)
        elif r == 3:
            vm.setNameLabel("name" + str(random.randint(100000)))
        elif r == 4:
            vm.setRam(vm.getRam() * 2)
        elif r == 5:
            vm.setRam(int(vm.getRam() / 2))
        else:
            vm.changeState(VirtualMachineState.ON)
        log.info("reconfigure %s" % r)

    def query_stats(self, u):
        """ """
        try:
            vapp_url = self._context.getApiContext().getEndpoint().toString() + "/admin/statistics/vappsresources/"
            vdc_url = self._context.getApiContext().getEndpoint().toString() + "/admin/statistics/vdcsresources/"
            self.query_statistics(vapp_url, u)
            self.query_statistics(vdc_url, u)
            log.info("statistics")
        except (AbiquoException, AuthorizationException), e:
            log.info("%s " % e.getMessage())
            
    def query_statistics(self, url, username):
        try:
            request = urllib2.Request(url)
            base64string = base64.encodestring('%s:%s' % (username, 'login')).replace('\n', '')
            request.add_header("Authorization", "Basic %s" % base64string)
            urllib2.urlopen(request)
        except (AbiquoException, AuthorizationException), e:
            log.info("%s " % e.getMessage())
    

    def action(self, app):
        """ Action on a vapp """
        log.info("%s" % app.getState())
        try:
            if app.getState() == VirtualApplianceState.DEPLOYED:
                log.info("undeploy")
                app.undeploy()
            elif app.getState() == VirtualApplianceState.NOT_DEPLOYED:
                log.info("deploy")
                app.deploy()
            elif app.getState() == VirtualApplianceState.NEEDS_SYNC:
                for m in app.listVirtualMachines():
                    r = random.randint(1, 7)
                    if r <= 4:
                        if m.getState() == VirtualMachineState.NOT_ALLOCATED:
                            m.deploy()
                        elif m.getState() == VirtualMachineState.ON:
                            m.changeState(VirtualMachineState.OFF)
                        elif m.getState() == VirtualMachineState.OFF:
                            self.reconfigure(m)
        except (AbiquoException, AuthorizationException), e:
            log.info("%s " % e.getMessage())
        log.info("action")

    def create_context_user(self, user):
        context = self.create_context_user_nick(user.getNick())
        return context

    def create_context_user_nick(self, userNick):
        context = ContextBuilder.newBuilder(AbiquoApiMetadata()) \
            .endpoint(str(self._context.getApiContext().getEndpoint())) \
            .credentials(userNick, "login") \
            .modules([JschSshClientModule(), NullLoggingModule()]) \
            .build(AbiquoContext)
        # Close context automatically when exiting
        atexit.register(self.__del__)
        return context 


def load():
    """ Loads the current plugin """
    return LoadPlugin()
