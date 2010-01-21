import dbutils as db
import rpy2.robjects as R

from pylab import *
from scipy import stats,array,log,linalg,ones,sqrt,zeros,repeat,\
    concatenate,dot

import DataMining as DM

pcolors=['b','g','r','c','m','y','k',
         'b-.','g-.','r-.','c-.','m-.','y-.','k-.',
         'b:','g:','r:','c:','m:','y:','k:',
         'b--','g--','r--','c--','m--','y--','k--',]


#### Standard Statistical Utility Functions ####

def E(data,weighted=False,alpha=0.05):
  """
  Given an array and an alpha, returns
    (E_bar,moe)
  where E_bar = sample mean of data, and
  moe = 1/2 size of the (1-alpha) Confidence Interval.

  If weighted is true, then E_bar is a weighted mean.
  In this case data should be an N-by-2 matrix, with
  each row of the form
    (data_value,weight).
  """

  if not weighted:
    E_bar = data.mean()
    moe = stats.t.ppf(1-alpha/2,len(data)-1) * data.std(ddof=1)/sqrt(len(data))
    
  else:
    w_total = data[:,1].sum()
    w_sum = dot( data[:,0],data[:,1] )
    E_bar = w_sum/w_total
    w_var = dot( (data[:,0]-E_bar)**2, data[:,1] ) / w_total
    w_sd = sqrt(w_var)
    moe = stats.t.ppf(1-alpha/2,len(data)-1) * w_sd / sqrt(len(data))
    print w_sd,w_total,moe,len(data)
    
  return E_bar,moe



def probability_make_transfer_sim(xdata,wdata,transfer_window,
                                  nsims = 100000):
  """
  Given R-Vector xdata representing instances and R-vector wdata
  representing weighted probabilities of those instances (need not
  add to 1, can be None for equal probability), and the
  transfer window in seconds (that is, the scheduled time between
  the arrival of two buses), calculates via siimulation the
  probability that you will make that transfer.
  """
  total_made = 0
  total_num = 0

  print "Sampling..."
  samples_per_sim = 2
  rref = R.r['sample'](xdata, nsims*samples_per_sim, replace = True,
                       prob = wdata)
  samples = array(rref)
  del rref
  print "Done."

  print "Simulating..."
  for iter in xrange(nsims):
    arrivals = samples[iter*samples_per_sim:(iter+1)*samples_per_sim]

    if arrivals[0] <= (arrivals[1]+transfer_window):
      total_made += 1
    total_num += 1

  print "Done."
  return float(total_made)/total_num


def p_make_transfer_vs_window(data,windows=linspace(-300,900,16),weighted=True):
  """
  Given optionally weighted lateness data and a set of transfer windows
  (in seconds), plots the likelihood of making a transfer against
  transfer window. Returns results.
  """

  xdata = R.FloatVector(data[:,0])
  if weighted:
    wdata = R.FloatVector(data[:,1])
  else:
    wdata = None

  probs=[]

  for window in windows:
     prob = probability_make_transfer_sim(xdata,wdata,window)
     probs.append(prob)
     
  probs = array(probs)
  figure()
  plot(windows,probs,'k-',label="P(make transfer)")
  #legend()
  xlabel("Transfer window (s)")
  ylabel("Probability of making transfer")
  title("Probability of making transfer vs transfer windows")
  return probs


def expected_wait_time_random_arrival(xdata,wdata,headway,
                                      nsims = 5000000, ntrips=3):
  """
  Given R-Vector xdata representing instances and R-Vector wdata
  representing weighted probabilities of those instances (need not
  add to 1, can be None for equal probability), and the headway in
  seconds of the bus, calculates via simulation the average wait time 
  for a person arriving at the stop at random.

  This function requires R-Vectors because otherwise a memory leak
  in the r2py package causes major problems if you call this function
  multiple times.
  """
  total_waits = 0.0
  total_num = 0

  print "Sampling..."
  samples_per_sim = 1+2*ntrips
  rref = R.r['sample'](xdata, nsims*samples_per_sim, replace = True,
                       prob = wdata)
  samples = array(rref)
  del rref
  print "Done."

  print "Simulating..."
  for iter in xrange(nsims):
    # your random arrival
    arrival_x = int( random() * (headway+1) ) - headway/2

    # the buses' random arrival
    latenesses = samples[iter*samples_per_sim:(iter+1)*samples_per_sim]
    arrivals = latenesses + arange(-ntrips,ntrips+1)*headway
    arrivals.sort()
    try:
      wait_time = arrivals[find(arrivals >= arrival_x)[0]] - arrival_x
      total_waits += wait_time
      total_num += 1
    except:
      print "WARNING: If you see this message a lot you need more trips!!!"

  print "Done."
  return total_waits/total_num

def calc_expected_wait_time_for_random_arrival(data,headways,weighted=True):

  xdata = R.FloatVector(data[:,0])
  if weighted:
    wdata = R.FloatVector(data[:,1])
  else:
    wdata = None

  ret = {}
  for headway in headways:
    ew = expected_wait_time_random_arrival(xdata,wdata,headway)
    print headway,ew
    ret[headway]=ew
  return ret


def expected_wait_time_simulation(xdata,wdata,arrival_x,headway,
                                  nsims = 500000, ntrips=3):
  """
  Given lateness data which is optionally weighted,
  the arrival time of one waiting for the bus, and the headway 
  for the route (i.e. the expected time between buses), computes
  by simulation the expected time that one will wait until a 
  bus arrives.

  xdata and wdata should be R Vectors!!! This is due to a memory leak
  in rpy2.

  nsims = number of iterations of simulation
  ntrips = number of arrivals placed before and after central trip.
           i.e., total number of arrivals will be ntrips*2 + 1.
           arrival_x is relative to the central trip.
  """
  
  ## We will use the R library to sample from our data, 
  ## with weighted probability distribution if provided.

  total_waits = 0.0
  total_num = 0
  

  print "Sampling..."
  samples_per_sim = 1 + 2*ntrips
  rref = R.r['sample'](xdata, nsims * samples_per_sim,replace = True,
                       prob = wdata)
  samples = array(rref)
  del rref
  print " done."

  print "Simulating..."

  for iter in range(nsims):
    latenesses = samples[iter*samples_per_sim:(iter+1)*samples_per_sim]

    # arrivals are the arrival times of all the buses relative
    # to the scheduled time of the central trip.
    arrivals = latenesses + arange(-ntrips,ntrips+1)*headway
    arrivals.sort()
    try:
      wait_time = arrivals[find(arrivals >= arrival_x)[0]] - arrival_x
      total_waits += wait_time
      total_num += 1
    except:
      print "WARNING: If you see this message a lot you need more trips!!!"

  print " done."

  return total_waits / total_num
  

def expected_wait_vs_arrival_plot(data,headways,min_arrival,
                                  weighted=True,ofile="simplot.png"):
  """
  Given an optionally weighted dataset, a set of headways (in seconds),
  and a minimum value for relative person arrival time (in seconds),
  plots expected wait time for that person for each value of headway,
  for personal arrival times from min_arrival to min_arrival+headway (i.e.
  one period).
  """
  xdata = R.FloatVector(data[:,0])
  if weighted:
    wdata = R.FloatVector(data[:,1])
  else:
    wdata = None
  ret = {}
  f=figure()
  for i,headway in enumerate(headways):
    print "Computing plot for headway",headway,"..."
    ew = []
    arrivals=linspace(min_arrival,min_arrival+headway+60,15)
    for arrival in arrivals:
      ew.append(expected_wait_time_simulation(xdata,wdata,arrival,headway))
    plot(arrivals,ew,pcolors[i],label="Headway="+str(headway))
    ewrandom = expected_wait_time_random_arrival(xdata,wdata,headway)
    plot( (arrivals[0],arrivals[-1]), (ewrandom,ewrandom),
          pcolors[i]+"--",
          label="For random arrival")

    ret[headway] = ew,ewrandom
  legend()
  xlabel("Your Arrival")
  ylabel("Expected Wait Time")
  title("Expected Wait Times vs Headway, Arrival")
  f.savefig(ofile)
  return ret



def ecdf(data,weighted=False,alpha=0.05):
  """
  Given an array and an alpha, returns 
     (x,p,a_n)
  x and p are arrays, where x are values in the sample space and p 
  is the corresponding cdf value.
  a_n is the margin of error according to the DKWM theorem using
  the supplied value of alpha. Interpreted, this means:
  
    P( {|cdf(x) - ecdf(x)| > a_n} ) <= alpha

  If weighted=True, then data should be a N-by-2 matrix,
  where each row contains 
    (data_pt, weight)
  where weight is as defined in the Horvitz-Thompson estimate.
  """
  if not weighted:
    dcopy = array(data)
    dcopy.sort()
    n=len(data)

    ret_x=repeat(dcopy,2)
    ret_p=concatenate(zip(linspace(0.0,float(n-1)/n,n),linspace(1./n,1.0,n)))
    a_n = sqrt( 1./(2*n) * log(2./alpha) )

  else:
    w_total = data[:,1].sum()
    sort_order = data[:,0].argsort()
    sorted = data[sort_order]
    
    ret_x = repeat(sorted[:,0],2)
    ret_p = concatenate(( [0.0],
                          repeat(1./w_total * cumsum(sorted[:-1,1]),2),
                          [1.0] ))
    a_n = sqrt( 1./(2*w_total) * log(2./alpha) )

  return ret_x,ret_p,a_n


def find_quantile(q,x,p):
  """
  Given x and p as returned by the ecdf function above,
  finds the q-quantile. Specifically, returns
    (x_q,p_q,i)
  where x_q is the q-quantile, p_q is the cumulative probability
  for that x-value (should be very close to q), and i is the index
  at which (x_q,p_q) was found.
  """
  ixs = find(p>=q)
  if len(ixs) == 0:
    i = len(x)-1
  else:
    i = ixs[0]
  return x[i],p[i],i

def evaluate_ecdf(x0,x,p):
  """
  Given x and p as returned by the ecdf function above, finds the
  value of the ecdf evaluated at x0. Specifically, returns
    (x_v,p_v,i)
  where x_v is the closest found x-value, p_v is the value of the ecdf
  at that point, and i is the index in x,p of these points.
  """
  i = find(x == x0)
  if len(i) == 0:
    i = max( 0,find(x > x0)[0]-1 )
  else:
    i = i[-1]
  return (x[i],p[i],i)

def find_pred_interval(x,p,a_n,alpha=0.05):
  """
  Given x, p and margin of error as returned by the ecdf function,
  finds and returns the prediction interval
    ( (lower, upper),
      (lower-lower_moe,upper+upper_moe) )
  where lower and upper are inside the x-space and represent capturing
  (1-alpha) of the distribution's area, and lower_moe and upper_moe
  represent the margin of error that is introduced from the ecdf's
  margin of error a_n.
  """

  # Finds the lowest possible alpha/2 quantile
  x_lolo,p_lolo,i_lolo = find_quantile(alpha/2,x,p+a_n)

  # Finds the central lower interval bound
  x_lo,p_lo,i_lo = find_quantile(alpha/2,x,p)
  
  # Finds the highest possible 1-alpha/2 quantile
  x_hihi,p_hihi,i_hihi = find_quantile(1-alpha/2,x,p-a_n)

  # Finds the central upper interval bound
  x_hi,p_hi,i_hi = find_quantile(1-alpha/2,x,p)
  
  return ( (x_lo,x_hi),
           (x_lolo, x_hihi) )


def diffmeanCI(d1,d2,weighted=False,alpha=.05):
  """
  Given two arrays and an alpha value, returns the 1-alpha confidence
  interval for the difference in means between the two arrays.
  More specifically, the return value is:
    ( (lower_norm,upper_norm) , (lower_satt,upper_satt) )
  where (lower_norm,upper_norm) is the CI assuming a normal distribution
  for the datasets, and (lower_satt,upper_satt) is the CI without assuming
  any particular distribution (i.e. using the Satterthwaite degrees of
  freedom).
  """
  n1,n2=len(d1),len(d2)
  xbar1,xbar2=d1.mean(),d2.mean()
  s1,s2=d1.std(ddof=1),d2.std(ddof=1)

  center = xbar1-xbar2

  # Assuming equal variances
  s=sqrt( ((n1-1)*s1**2+(n2-1)*s2**2) / (n1+n2-2) )
  moe1 = stats.t.ppf(1-alpha/2,n1+n2-2)*s*sqrt(1./n1+1./n2)  

  # Using Satterthwaite DOF
  w1,w2=d1.var(ddof=1)/n1,d2.var(ddof=1)/n2
  nu=((w1+w2)**2)/(w1**2/(n1-1)+w2**2/(n2-1))
  moe2 = stats.t.ppf(1-alpha/2,nu)*sqrt(s1**2/n1+s2**2/n2)

  return ( (center-moe1,center+moe1), 
           (center-moe2,center+moe2) )





def compare_ecdfs(attrsplit,rows,
                  plot_CIs=True,
                  plot_Es=False,
                  plot_E_CIs=False,
                  col_name='lateness',
                  alpha=0.05):
  """
  Given a set of rows to split, and the attributes on which to split them,
  compares distributions and expectations on a plot (with optional 
  confidence intervals).
  If rows are already split into a dict, then just put the partitioning
  column for attrsplit.
  """

  if isinstance(rows,dict):
    split = rows
  else:
    print "Splitting..."
    split = DM.split_on_attributes(attrsplit,rows)
    print "OK."

  
  figure()
  for i,key in enumerate(split.keys()):
    rows=array([(r[col_name],r['trip_stop_weight']) for r in split[key]])    
    x,p,a_n = ecdf(rows,weighted=True,alpha=alpha/len(split)) #bonferroni
    plot(x,p,pcolors[i],label=str(key));
    print key,"ECDF MOE:",a_n

    if plot_CIs:
      plot(x,p-a_n,pcolors[i]+'--',label=None)
      plot(x,p+a_n,pcolors[i]+'--',label=None)

    E_bar,moe = E(rows,weighted=True,alpha=alpha/len(split)) #bonferroni
    print key,"E:",E_bar,", E MOE:",moe
    if plot_Es:
      plot((E_bar,E_bar),(0,1),pcolors[i],label=None)
    if plot_E_CIs:
      plot((E_bar-moe,E_bar-moe),(0,1),pcolors[i]+'--',label=None)
      plot((E_bar+moe,E_bar+moe),(0,1),pcolors[i]+'--',label=None)
  
  xlabel(col_name)
  ylabel("CDF("+col_name+")")
  title("ECDF of "+col_name+" partitioned by "+str(attrsplit))
  



#### Static Analyses ####

def compare_vehicle_type(rows=None):
  """Compare lateness distributions between vehicle types"""
  
  if rows is None:
    cur = db.get_cursor()
    sql = """
select vehicle_type,lateness,trip_stop_weight
from datamining_table natural join trip_stop_weights
where lateness is not null
"""
    print "Selecting..."
    db.SQLExec(cur,sql)
    print "Retrieving..."
    rows = cur.fetchall()
    cur.close()
    print len(rows),"rows retrieved."
    
  compare_ecdfs(('vehicle_type',),rows)



def compare_routenames(rows=None):
  """Compare lateness distributions between route ID's"""
  
  if rows is None:
    cur = db.get_cursor()
    sql = """
select route_name, lateness, trip_stop_weight
from datamining_table natural join trip_stop_weights
where lateness is not null
"""
    print "Selecting..."
    db.SQLExec(cur,sql)
    print "Retrieving..."
    rows = cur.fetchall()
    cur.close()
    print len(rows),"rows retrieved."

  compare_ecdfs(('route_name',),rows)


def compare_dows(rows=None):
  """Compares lateness distributions between days of the week"""

  if rows is None:
    cur = db.get_cursor()
    sql = """
select date_part('dow',trip_date) as wday, lateness, trip_stop_weight 
from datamining_table 
  natural join trip_stop_weights
  natural join gps_segments
where lateness is not null
"""
    print "Selecting..."
    db.SQLExec(cur,sql);
    print "Retrieving..."
    rows = cur.fetchall()
    cur.close();
    print len(rows),"rows retrieved."

  compare_ecdfs(('wday',),rows)
  return rows

def compare_hour_of_weekday(rows=None):
  """Compares lateness distributions between hours of the weekday"""
  
  if rows is None:
    cur = db.get_cursor()
    sql = """
select scheduled_hour_of_arrival as hoa, lateness, trip_stop_weight
from datamining_table natural join trip_stop_weights
where lateness is not null and service_id='1'
"""
    print "Selecting..."
    db.SQLExec(cur,sql)
    print "Retrieving..."
    rows = cur.fetchall()
    cur.close()
    print len(rows),"rows retrieved."

  compare_ecdfs(('hoa',),rows)


def compare_route_portion(rows=None):
  """Compares lateness distributions between portions of the route"""

  if rows is None:
    cur = db.get_cursor()
    print "Selecting..."
    sql = """
select stop_number, total_num_stops, total_num_stops-stop_number as stops_before_end, (100*stop_number::numeric/total_num_stops)::int as route_portion, lateness, trip_stop_weight 
from datamining_table dm 
  natural join trip_stop_weights 
  natural join gps_segments 
  inner join (select count(*) as total_num_stops, trip_id 
              from gtf_stop_times 
              group by trip_id) ns 
    on ns.trip_id = dm.gtfs_trip_id 
where lateness is not null
"""
    db.SQLExec(cur,sql)
    print "Retrieving..."
    rows = cur.fetchall()
    cur.close()
    print len(rows),'rows fetched.'

  # Plot ECDF comparisons
  stop_num_split = DM.split_on_attributes(('stop_number',),rows)
  end_num_split = DM.split_on_attributes(('stops_before_end',),rows)
  halfway_split = DM.split_on_attributes(('route_portion',),rows)

  cdf_dict = { "Second stop" : stop_num_split[(1,)],
               "Middle stop" : halfway_split[(50,)]+halfway_split[(51,)],
               "Next to last stop" : end_num_split[(1,)] }
  compare_ecdfs("Stop Position",cdf_dict);

  # Plot E vs stop number
  Es = []
  moes = []
  sns = array([k[0] for k in stop_num_split.keys()])
  sns.sort()
  for sn in sns:
    rowdata = array([(r['lateness'],r['trip_stop_weight']) for r in stop_num_split[(sn,)]])
    Eval,moe = E(rowdata,weighted=True)
    Es.append(Eval)
    moes.append(moe)
  Es = array(Es)
  moes = array(moes)
  
  figure()
  plot(sns,Es,'k-',label="Estimated expectation")
  plot(sns,Es+moes,'k--',label=None)
  plot(sns,Es-moes,'k--',label=None)
  #legend()
  xlabel("Stop Number")
  ylabel("Expected Latenes")
  title("Expected Lateness vs Stop Number")





def critical_mass_compare(diffrows,rows):
  """
  Given the rows returned by criticalmass_compare_rows(),
  compares ECDFs and CI's for mean difference.
  """
  compare_ecdfs(('is_cmass',),rows)
  diffdata = array([(r['ldiff'],r['trip_stop_weight']) for r in diffrows])
  Ediff,moe = E(diffdata,weighted=True)
  return Ediff,moe


def criticalmass_compare_rows():
  """
  Selects and pairs rows from the same trip where one is from
  March 27 and the others are not (this is a many-to-one pairing),
  and subtracts their latenesses as the column 'ldiff'.

  Also selects all latenesses with a column 'is_cmass' indicating
  0 for not-cmass days and 1 for cmass days, for an ecdf comparison
  split.
  """

  print "Selecting..."
  cur = db.get_cursor()
  db.SQLExec(cur,
             """
select (dm_cm.lateness - dm.lateness) as ldiff, trip_stop_weight
from 
datamining_table dm_cm natural join trip_stop_weights
inner join gps_segments gs_cm on dm_cm.gps_segment_id=gs_cm.gps_segment_id
  and gs_cm.trip_date = '2009-03-27'
inner join datamining_table dm on dm.gtfs_trip_id=dm_cm.gtfs_trip_id
  and dm.stop_sequence=dm_cm.stop_sequence
inner join gps_segments gs on dm.gps_segment_id=gs.gps_segment_id
  and gs.trip_date != '2009-03-27'
where dm_cm.lateness is not null and dm.lateness is not null
and dm_cm.route_name in ('1','9','19')
             """);
  print "Retrieving..."
  diffrows=cur.fetchall();
  print len(diffrows),"rows retrieved."

  print "Selecting..."
  db.SQLExec(cur,
             """
select lateness, trip_stop_weight,
case when trip_date='2009-03-27' then 1
     else                             0
end as is_cmass
from datamining_table natural join gps_segments 
  natural join trip_stop_weights
where lateness is not null and service_id='1'
""");
  print "Retrieving..."
  rows = cur.fetchall();
  print len(rows),'rows retrieved.'
  cur.close();

  return diffrows,rows









def independent_sampling_cdf(rows=None):
  
  if rows is None:
    cur = db.get_cursor();
    rows = []
    print "Selecting..."
    # For each gps_segment we want to randomly select a sample
    for i in range(58903):
      if (i+1)%(58903/100)==0:
        print " %d/%d"%(i+1,58903)
      if random() < 0.5: 
        continue
      db.SQLExec(cur,
"""select lateness,trip_stop_weight 
   from datamining_table dm natural join trip_stop_weights tsw
     where gps_segment_id=%(gseg)s and lateness is not null 
     order by random() limit 1""",
                 {'gseg':i});
      if cur.rowcount > 0:
        srow = cur.fetchall()[0]; #should be just one
        rows.append(srow)
    cur.close()
    print len(rows),"rows retrieved."

  try:
    data = array([(r['lateness'],r['trip_stop_weight']) for r in rows])
    x,p,a_n = ecdf(data,weighted=True)
  
    figure()
    plot(x,p,'k',label="Independent")
    plot(x,p+a_n,'k--',label=None)
    plot(x,p-a_n,'k--',label=None)
    xlabel("lateness")
    ylabel("CDF(lateness)")
    title("CDF of Lateness for Independent Samples")
  except e:
    print e

  return rows









# scratch note, to run just one query for all the comparisons
comparison_sql = """
select service_id,date_part('dow',trip_date) as wday, 
  scheduled_hour_of_arrival as hoa, stop_number, 
  total_num_stops-stop_number as stops_before_end, total_num_stops, 
  (100*stop_number::numeric/total_num_stops)::int as route_portion, 
  lateness, trip_stop_weight 
from datamining_table 
  natural join trip_stop_weights 
  natural join gps_segments 
  inner join (select count(*) as total_num_stops, trip_id 
              from gtf_stop_times 
              group by trip_id) ns 
    on ns.trip_id = datamining_table.gtfs_trip_id 
where lateness is not null
"""



#### Dynamic Analyses ####


def depict_predinterval_calculation(rows=None,degsep=1,cond=60,alpha=0.05):
  """
  Creates a plot explaining how the prediction interval calculations
  work.
  """
  
  if rows is None:
    print "Selecting..."
    cur = db.get_cursor()
    db.SQLExec(cur,"""
select d2.lateness, trip_stop_weight
from datamining_table d2
natural join trip_stop_weights
inner join datamining_table d1
  on d1.gps_segment_id = d2.gps_segment_id
  and d2.stop_number-d1.stop_number=%(degsep)s
  and d1.lateness = %(cond)s
  and d2.lateness is not null and d1.lateness is not null
""",  {'degsep':degsep,'cond':cond});

    print "Retrieving..."
    rows = cur.fetchall();
    cur.close()
    print len(rows),"rows retrieved."


  figure()

  rowdata = array([(r['lateness'],r['trip_stop_weight']) for r in rows])
  x,p,a_n = ecdf(rowdata,weighted=True)
  
  plot(x,p,'k-',label="Conditional ECDF")
  plot(x,p+a_n,'k--',label="ECDF 95% CI")
  plot(x,p-a_n,'k--',label=None)
  
  (lower,upper),(lolo,upup) = find_pred_interval(x,p,a_n,alpha=alpha)

  plot( (lower,lower),(0,alpha/2), 'r-',label="Lower interval bound")
  plot( (-2000,lower),(alpha/2,alpha/2), 'r-',label=None)

  plot( (upper,upper),(0,1-alpha/2),'g-',label="Upper interval bound")
  plot( (-2000,upper),(1-alpha/2,1-alpha/2),'g-',label=None)

  plot( (lolo,lolo),(0,alpha/2), 'c-',label="Lower bound CI")
  #plot( (-2000,lolo),(alpha/2,alpha/2), 'c-',label=None)

  plot( (upup,upup),(0,1-alpha/2),'m-',label="Upper bound CI")
  #plot( (-2000,upup),(1-alpha/2,1-alpha/2),'m-',label=None)

  legend()
  xlabel("Lateness")
  ylabel("ECDF(Lateness)")
  title("Prediction Interval Calculation")



def conditional_lateness_prediction_intervals(rows=None,
                                              degrees_sep=(1,5,10,20,50),
                                              alpha=0.05):

  if rows is None:
    print "Selecting..."
    cur = db.get_cursor()
    db.SQLExec(cur,"""
select 30*(d1.lateness/30.0)::int as conditional, d2.stop_number-d1.stop_number as sepdegree,
  d2.lateness, trip_stop_weight
from datamining_table d2
natural join trip_stop_weights
inner join datamining_table d1
  on d1.gps_segment_id = d2.gps_segment_id
  and d2.stop_number-d1.stop_number in (""" + \
                 ",".join(map(str,degrees_sep)) + """)
  and d2.lateness is not null and d1.lateness is not null
""")
    print "Retrieving..."
    rows = cur.fetchall()
    cur.close()
    print len(rows),"rows retrieved."

  figure()

  sep_split = DM.split_on_attributes(('sepdegree',),rows)
  sds = array([k[0] for k in sep_split.keys()])
  sds.sort()
  for i,sd in enumerate(reversed(sds)):
    sdrows = sep_split[(sd,)]
    cond_split = DM.split_on_attributes(('conditional',),sdrows)
    conds = array([k[0] for k in cond_split.keys()])
    conds.sort()
    
    upper_preds = []
    lower_preds = []
    upup_preds = []
    lolo_preds = []
    for cond in conds:
      cond_rows = array([(r['lateness'],r['trip_stop_weight']) 
                         for r in cond_split[(cond,)]])
      x,p,a_n = ecdf(cond_rows,weighted=True)
      (lower,upper),(lolo,hihi) = find_pred_interval(x,p,a_n,alpha=alpha)
      upper_preds.append(upper)
      lower_preds.append(lower)
      

      upup_preds.append(hihi)
      lolo_preds.append(lolo)

    #plot(conds,upper_preds,pcolors[i],label="D.o.S="+str(sd))
    #plot(conds,lower_preds,pcolors[i],label=None)
    plot(conds,upup_preds,pcolors[i]+'+-',label="D.o.S="+str(sd))
    plot(conds,lolo_preds,pcolors[i]+'+-',label=None)
      
  legend()
  xlabel("Conditional Lateness")
  ylabel("Lateness Prediction Interval")
  title("%d%% Prediction Intervals vs. Stop Separation, Prev Lateness"%(100*(1-alpha),))


def conditional_lateness_gained(rows=None,
                               degrees_sep=1,
                               conds=(-6,0,6,60,120)):
  
  if rows is None:
    print "Selecting..."
    cur = db.get_cursor()
    db.SQLExec(cur,"""select d1.lateness_gained as cond,d2.lateness_gained,
trip_stop_weight 
from datamining_table d1 inner join datamining_table d2
  on d1.gps_segment_id=d2.gps_segment_id
  and d1.stop_number+%(deg_sep)s=d2.stop_number
  and d1.lateness_gained in (""" + ",".join(map(str,conds)) + """)
  and d2.lateness_gained is not null
inner join trip_stop_weights tsw on d2.gtfs_trip_id = tsw.gtfs_trip_id
  and d2.stop_id = tsw.stop_id
""",
               {'deg_sep':degrees_sep});
    print "Retrieving..."
    rows = cur.fetchall()
    cur.close()
    print len(rows),"rows retrieved."

  try:
    compare_ecdfs(('cond',),rows,col_name='lateness_gained',
                  plot_CIs=True,plot_Es=False,plot_E_CIs=False)
  except e:
    print e
  return rows



def conditional_lateness_plots(rows=None,
                               degrees_sep=1,
                               conds=(0,60,300,600,1200)):
  """
  Plots the (weighted) conditional lateness distribution as
  
    F( lateness at stop | lateness at Dth stop previous )
    
  where D = degrees_sep. This is plotted as conditioned on each of
  the latenesses provided in conds.
  """

  if rows is None:
    cur = db.get_cursor();
    print "Selecting..."
    db.SQLExec(cur,"""select d1.lateness as cond,d2.lateness,trip_stop_weight 
from datamining_table d1 inner join datamining_table d2
  on d1.gps_segment_id=d2.gps_segment_id
  and d1.stop_number+%(deg_sep)s=d2.stop_number
  and d1.lateness in (""" + ",".join(map(str,conds)) + """)
  and d2.lateness is not null
inner join trip_stop_weights tsw on d2.gtfs_trip_id = tsw.gtfs_trip_id
  and d2.stop_id = tsw.stop_id
""",
               {'deg_sep':degrees_sep});
    print "Retrieving..."
    rows = cur.fetchall()
    cur.close()
    print len(rows),"rows retrieved."

  try:
    compare_ecdfs(('cond',),rows)
  except e:
    print e
  return rows


def measure_slowness_correlation(rows=None):
  """
  Measures the correlation of normalized travel time between sequential
  segments.
  """
  if rows is None:
    rows = DM.get_joined_rows(prev_attrs=("meannorm_ssls as prev_stds",),
                              degree_of_sep=1);

  max = rows.rowcount
  prev_stds = zeros(max)
  stds = zeros(max)
  n = 0

  print "running manually..."
  for k,row in enumerate(rows):
    if k%(max/100) == 0:
      print "%5.2f%% (%d/%d) Done (n=%d)..."%(100*float(k)/max,k,max,n)
    prev_stds[n] = row['prev_stds']
    stds[n] = row['meannorm_ssls']
    if row['prev_stds'] is not None and row['meannorm_ssls'] is not None: 
      n += 1

  print "Calculating correlation..."
  corr = R.r['cor'](R.FloatVector(prev_stds[:n]),
                    R.FloatVector(stds[:n]))
  rows.close()

  return corr,prev_stds,stds



res_ewait = {300: ([225.021894,
        226.63841828442645,
        226.05250457054819,
        228.3526068549352,
        227.52869714505852,
        229.08866742950582,
        229.54039971558609,
        228.19271800000001,
        228.41869428441788,
        226.49241257053473,
        226.46926685495501,
        224.07704114499225,
        224.87847942944285,
        225.66833371556882,
        225.25969599999999],
       226.46945829389165),
 600: ([385.140468,
        374.56255285752536,
        365.04768171194866,
        358.9296485692945,
        357.87632143070329,
        360.36018628791663,
        367.98161714262318,
        381.11043000000001,
        397.0368248579847,
        407.10351971087545,
        409.37601456903712,
        406.00087543095492,
        395.48639228884571,
        382.66164714231309,
        370.62472200000002],
       381.24983859999998),
 900: ([443.70171800000003,
        423.08441943103395,
        423.1897228584528,
        439.55437228979952,
        474.85283770952577,
        528.21809914011851,
        585.96208657096315,
        620.23552800000004,
        630.41524742719344,
        614.67872686069791,
        578.78254028975527,
        535.39358370862351,
        488.64125514057406,
        448.75868456886911,
        423.332266],
       521.19431580000003),
 1200: ([466.89103999999998,
         456.435518,
         489.62153000000001,
         566.04258000000004,
         685.530348,
         801.310024,
         863.56086400000004,
         866.14851199999998,
         826.27934200000004,
         765.60573999999997,
         692.92793400000005,
         618.95193800000004,
         543.91690000000006,
         482.04592600000001,
         454.12408799999997],
        660.590912),
 1800: ([494.63929400000001,
         546.15524313991227,
         739.66406228518088,
         1061.2605794173724,
         1313.1383805745056,
         1382.8266737224997,
         1334.7329008517311,
         1240.502502,
         1128.4755371399333,
         1006.760060280792,
         881.22312542032478,
         754.15822057677781,
         632.1414637120331,
         527.2643308598856,
         499.08978200000001],
        945.41581040000005),
 2100: ([508.13229999999999,
         613.33199971145257,
         941.84975741918674,
         1400.4880651504243,
         1630.5615588434405,
         1625.13663856737,
         1531.9599182766408,
         1405.0440880000001,
         1264.3053337216706,
         1116.5285994189642,
         967.93784313748949,
         819.30576686193763,
         673.98771257434987,
         548.73005829090539,
         520.42697799999996],
        1090.6142248000001),
 3600: ([564.25454000000002,
         1235.3034685768512,
         2626.4430711490477,
         3007.0123396931949,
         2891.9512943035838,
         2675.3321028523633,
         2428.9744454425563,
         2176.7411499999998,
         1919.1412825627717,
         1659.0085411571963,
         1398.4152417226016,
         1140.3198062793674,
         884.07210886220957,
         644.73765742666831,
         619.26800400000002],
        1825.0092325999999)};