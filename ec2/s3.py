import boto.s3
from boto.s3.key import Key

def find_bucket(bucket_name):
   # Use access key to access secure buckets!
   # s3 = boto.connect_s3(aws_access_key_id='your_access_key', aws_secret_access_key='your_secret_key')
   s3 = boto.connect_s3()
   
   bucket = s3.lookup(bucket_name)
   
   if bucket:
      print 'Bucket (%s) found' % bucket_name
   else:
      print 'Bucket (%s) not found' % bucket_name
   return bucket
   
   
def save(bucket, key_name, data):
   k = Key(bucket)
   k.key = key_name
   k.set_contents_from_string(data)
   print "Saved a new key to the bucket"
   
   
b = find_bucket('psd-jenkins-releases')
save(b, 'foo', 'bar')
