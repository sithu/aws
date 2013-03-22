import time
import boto.ec2
import subprocess
from boto.ec2.connection import EC2Connection
from boto.ec2.address import Address
from boto.vpc import VPCConnection
from config import config

KEY = config['aws_access_key_id']
SECRET = config['aws_secret_access_key']

def connect(region=config['region']):
   conn = boto.ec2.connect_to_region(region)
   print conn
   return conn

def vpc_connect(region_name=config['region']):
   region = boto.ec2.get_region(region_name=region_name)
   print region
   vpcconn = VPCConnection(aws_access_key_id=KEY, aws_secret_access_key=SECRET, region=region)
   print vpcconn
   
   return vpcconn

def create_eip(conn, in_vpc=False):
   domain = None
   if in_vpc:
      domain = 'vpc'
      
   address = conn.allocate_address(domain)
   print "Created a new EIP :", address
   return address

def create_vpc_gateway_router(vpcconn, cidr_block):
   '''
   One VPC can have 1-1 relationship to the following components: 
   - Subnets
   - Security Groups
   - Network ACLs
   - DHCP Options Sets
   - Network Interfaces
   - Route Tables
   - Internet Gateways
   - VPN Attachments
   So, deleting a VPC will also delete any above associated components.
   '''
   # 1. Create a VPC
   vpc = vpcconn.create_vpc(cidr_block)
   print "Created a new VPC (id:%s)" % vpc.id
   print vpc
   
   # 2. Create a Internet Gateway
   gateway = vpcconn.create_internet_gateway()
   print "Created a new Internet Gateway (id:%s)" % gateway.id
   print gateway
   
   # 3. Create a Route Table
   routetable = vpcconn.create_route_table(vpc.id)
   print "Created a new Route Table (id:%s) in VPC (id:%s)" % (routetable.id, vpc.id)
   print routetable
   
   return { 'vpc' : vpc, 'internet_gateway' : gateway, 'routetable' : routetable }
 
def create_security_group(conn, name, desc, vpc_id=None):
   sg = conn.create_security_group(name, desc, vpc_id)
   print "Created a new security group (id:%s)" % sg.id
   # TODO: Create security rules
   
   return sg
     
def create_subnet(vpcconn, vpc_id, cidr_block, availability_zone=config['zone']):
   subnet = vpcconn.create_subnet(vpc_id, cidr_block, availability_zone)
   print "Created a new subnet (id:%s) in VPC(id:%s)" % (subnet.id, vpc_id)
   print subnet
   
   return subnet
   
   
def setup_vpc(vpcconn, vpc_id=None, subnet_id=None, route_table_id=None, internet_gateway_id=None, destination_cidr_block='0.0.0.0/0'):
   print "Associating route table (%s) with subnet (%s)" % (route_table_id, subnet_id)
   vpcconn.associate_route_table(route_table_id, subnet_id)
   print "Associated route table (%s) with subnet (%s)" % (route_table_id, subnet_id)
   
   print "Attaching internet gateway (%s) with VPC (%s)" % (internet_gateway_id, vpc_id)
   vpcconn.attach_internet_gateway(internet_gateway_id, vpc_id)
   print "Attached internet gateway (%s) with VPC (%s)" % (internet_gateway_id, vpc_id)
   
   print "Adding a new route to the internet gateway (%s) to the route table (%s)" % (internet_gateway_id, route_table_id)
   vpcconn.create_route(route_table_id, destination_cidr_block, internet_gateway_id)
   print "Added a route to the route table."
   
   print "VPC is now ready to deploy instances!"
   

def create_instance(conn, ami_id, instance_name=None, vpc_subnet_id=None):
   key_pair_name = config['key_pair_name']
   security_group_ids = config['security_group_ids']
   instance_type = config['instance_type']
 
   reservation = conn.run_instances( image_id=ami_id,
                                    min_count=1,
                                    max_count=1,
                                    key_name=key_pair_name, 
                                    security_group_ids=security_group_ids,
                                    instance_type=instance_type,
                                    subnet_id=vpc_subnet_id)
   i = reservation.instances[0]
   
   print "Creating new instance:", i
       
   while i.state == u'pending':
      print "Launching new instance..."
      time.sleep(10)
      i.update()
   
   if instance_name:
      print "Tagging the new instance's name to ", instance_name
      conn.create_tags([i.id], {"Name":instance_name})
      
   print "A new instance (%s) was created." % i.id
   return i.id


def bind_elastic_ip_to_instance(conn, instance_id, allocation_id):
   print "Binding EIP(allocation_id=%s) to instance (%s)" % (allocation_id, instance_id)
   result = conn.associate_address(instance_id, allocation_id=allocation_id, allow_reassociation=True)
   if result:
      print "Binding success"
   else:
      print "Binding failed"
  
    
def ping(host, wait=60):
   print "Waiting for %d sec the host to be up..." % wait  
   time.sleep(wait)
   ping = subprocess.Popen(
       ["ping", "-c", "4", host],
       stdout = subprocess.PIPE,
       stderr = subprocess.PIPE)

   out, error = ping.communicate()
   print out
       
def vpc():
   conn = connect()
   vpcconn = vpc_connect()
   
   vgr = create_vpc_gateway_router(vpcconn, '10.10.0.0/16')
   
   vpc = vgr['vpc']
   routetable = vgr['routetable']
   internetgateway = vgr['internet_gateway']
   
   sg = create_security_group(conn, 'psd-refapp-test-sg', 'Test Security Group for PSD', vpc.id)
   
   subnet = create_subnet(vpcconn, vpc.id, config['cidr_block'])
   
   setup_vpc(vpcconn, vpc.id, subnet.id, routetable.id, internetgateway.id)
   
       
def new_instance():
   conn = connect()
   # Without VPC subnet_id, it will create a EC2 instance instead. 
   instance_id = create_instance(conn, config['ami_id'], config['instance_name'], config['subnet_id'])
   # Create a new EIP
   add = create_eip(conn, True)
   print "New EIP 'allocation_id':%s" % add.allocation_id
   bind_elastic_ip_to_instance(conn, instance_id, add.allocation_id)
   ping(add.public_ip)


#vpc()
new_instance()

''' 
Create VPC and Security Group (Network ACL is not needed for the public subnet only model.)
Create Subnet for the VPC
Create Internet Gateway
1. Attach Internet Gateway to VPC
2. Create EIP (so that we can later assign to a instance)
3. Create Route Table for the VPC
4. Add a new entry in the route table to route this destination (0.0.0.0/0) to the Internet Gateway
'''
