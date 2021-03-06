#!/usr/bin/env python


'''
Script to create or modify existing CloudWatch alarms

usage: put_metric_alarm.py --help
Author: Jussi Heinonen
Date: 9.3.2017
URL: https://github.com/Financial-Times/collective
'''

import sys, boto3, pprint, yaml, argparse, re, os, requests
import common
alarms_file = 'alarms.yml'
config_is_file = True

def put_metric_alarm(alarmprefix, namepace, description, actions, metric_name, threshold, statistic, operator, dimensions):
    # Construct string out of dimensions and append it to alarm name
    str_dimensions = ''
    for list_item in dimensions:
        str_dimensions = str_dimensions + "." + list_item['Value']
    common.info("Alarm name: " + alarmprefix + "." + metric_name + str_dimensions)
    
    client = boto3.client('cloudwatch', region_name=region_name)
    response = client.put_metric_alarm(
        AlarmName=alarmprefix + "." + metric_name + str_dimensions,
        AlarmDescription=description,
        OKActions=actions,
        AlarmActions=actions,
        InsufficientDataActions=actions,
        ActionsEnabled=True,
        MetricName=metric_name,
        Namespace=namespace,
        Dimensions=dimensions,
        Period=300,
        EvaluationPeriods=1,
        Threshold=threshold,
        Statistic=statistic,
        ComparisonOperator=operator
    )
    for each in response.itervalues():
        if each['HTTPStatusCode'] == 200:
            common.info("Alarm " + alarmprefix + "." + metric_name + str_dimensions + " created")
            return True
        else:
            common.error("Failed to create alarm " + alarmprefix + "." + metric_name + str_dimensions)
            return False
    pprint.pprint(response)

parser = argparse.ArgumentParser(description='Create CloudWatch alarms with given name prefix')
parser.add_argument('--alarmprefix', help='Alarm name prefix, eg. com.ft.up.semantic-data.neo4j ', required=True)
parser.add_argument('--namespace', help='[Optional] Metric namespace, eg. com.ft.up.semantic-data.neo4j', required=False)
parser.add_argument('--instanceid', help='[Optional] InstanceID, eg. i-0fc52a4ca4d81b5b4', required=False)
parser.add_argument('--topic', help='[Optional] ARN of SNS Topic to send alerts to, eg. arn:aws:sns:eu-west-1:027104099916:SemanticMetadata', required=False)
parser.add_argument('--config', help='[Optional] File path (./config/alarms.yml) or URL (https://raw.githubusercontent.com/Financial-Times/collective/master/alarms.yml) to alarm configuration YAML file', required=False)
parser.add_argument('--region', help='[Optional] AWS region, eg. eu-west-1', required=False)
args = parser.parse_args()
namespace = args.namespace
instance_id = args.instanceid
try:
    if args.region:
        region_name = args.region
    else:
        region_name = common.metadata_get_region('http://169.254.169.254/latest/meta-data/placement/availability-zone/')
    if args.config: # Check whether --config value is URL or a file
        if re.search("http",args.config):
            common.info("Getting config file from HTTP endpoint " + args.config)
            try:
                r = requests.get(args.config)
                if r.status_code == requests.codes.ok:
                    cfg = yaml.load(r.text)
                    config_is_file = False
                else:
                    common.error("Failed to load document " + args.config)
                    sys.exit(1)
            except Exception, e:
                common.error("Failed to retrieve yaml document from " + args.config + ". Reason: " + str(e) )
                sys.exit(1)
        else:
            if os.path.isfile(args.config):
                common.info("Using config file " + args.config)
                with open(args.config, 'r') as ymlfile:
                    cfg = yaml.load(ymlfile)
                common.info("File " + args.config + " loaded")
            else:
                common.error("File " + args.config + " not found!")
                sys.exit(1)
    else:
        common.info("Using default config file " + alarms_file)
        with open(alarms_file, 'r') as ymlfile:
            cfg = yaml.load(ymlfile)
        common.info("File " + alarms_file + " loaded")
    for each in cfg.itervalues():
        if args.namespace:
            namespace = args.namespace
        elif 'Namespace' in each:
            namespace = each['Namespace']
        else:
            common.error("Namespace of metric to create alarm for undefined. Use --namespace switch or set namespace key in configuration file")
            sys.exit(1)
        if args.instanceid:
            common.info("--instanceid argument is deprecated. Unique characteristics of alarm now extracted from dimensions")
        if args.topic: #Override AlarmActions if --topic is passed in as a parameter
            common.info("Using override topic " + args.topic)
            each['AlarmActions'] = [ args.topic ]
        elif not 'AlarmActions' in each: # Disable email alarms by setting invalid SNS Topic ARN
            sns_topic = common.construct_invalid_sns_topic(region_name)
            each['AlarmActions'] = [ sns_topic ]
        if "Dimensions" in each:
            dimensions = common.process_dimensions(each['Dimensions'])
        else:
            common.error("Unable to find dimensions key for alarm " + str(each))
            sys.exit(1)
        put_metric_alarm(
        args.alarmprefix,
        namespace,
        each['AlarmDescription'],
        each['AlarmActions'],
        each['MetricName'],
        each['Threshold'],
        each['Statistic'],
        each['ComparisonOperator'],
        dimensions)
except Exception, e:
    common.error("Error while creating alarms: " + str(e))
    sys.exit(1)
