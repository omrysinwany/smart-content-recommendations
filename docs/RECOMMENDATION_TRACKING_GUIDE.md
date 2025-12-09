# 🔍 Recommendation Tracking Guide

Your Smart Content Recommendation system now tracks **which algorithms recommend which content to which users**! Here's how to use this powerful new feature.

## 🎯 **What You Can Track**

✅ **Algorithm Performance** - See which algorithms work best  
✅ **Content Recommendations** - Track which content gets recommended by which algorithm  
✅ **User Interactions** - See how users respond to different algorithms  
✅ **Real-time Analytics** - Monitor performance as it happens  
✅ **A/B Testing** - Compare algorithm effectiveness  

## 📊 **Available Tools**

### **1. Recommendation Tracker (Visual Interface)**
```bash
python recommendation_tracker.py
```

**Features:**
- 📈 **Live Performance Monitor** - Real-time algorithm metrics
- 📊 **Recommendation History** - See all recent recommendations  
- 🤖 **Algorithm Comparison** - Compare CTR, engagement, speed
- 📄 **Content Analysis** - See how algorithms recommend specific content
- 🎯 **Test Generator** - Create sample recommendations for testing

### **2. API Endpoints (For Integration)**

#### **Get Recommendation History**
```bash
GET /api/v1/analytics/recommendations/history
```
**Query Parameters:**
- `user_id` - Filter by user
- `algorithm` - Filter by algorithm  
- `content_id` - Filter by content
- `days_back` - Time period (default: 7 days)
- `limit` - Max results (default: 50)

#### **Algorithm Performance**
```bash
GET /api/v1/analytics/algorithms/performance?days_back=7
```
**Returns:**
- Click-through rates (CTR)
- Engagement metrics
- Response times
- Unique content coverage

#### **Content Recommendation Analytics**
```bash
GET /api/v1/analytics/content/{content_id}/recommendations
```
**Shows:** Which algorithms recommended specific content and outcomes.

#### **User Recommendation History**
```bash
GET /api/v1/analytics/users/{user_id}/recommendations
```
**Shows:** What algorithms have been recommending to a specific user.

## 🚀 **Quick Start**

### **Step 1: Generate Some Recommendations**
```bash
# Create recommendations to populate tracking data
python recommendation_tracker.py

# Choose option 4: "Generate Test Recommendations"
# This will create sample data across all algorithms
```

### **Step 2: View the Results**
```bash
# Option 1: Visual interface
python recommendation_tracker.py

# Option 2: Direct API calls
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/v1/analytics/algorithms/performance"
```

### **Step 3: Analyze Algorithm Performance**
The tracker shows you:
- **Which algorithm** has the highest click-through rate
- **Which content** gets recommended most by each algorithm  
- **How fast** each algorithm generates recommendations
- **User engagement** patterns by algorithm

## 📈 **What You'll See**

### **Algorithm Performance Table**
```
🤖 Algorithm Performance (Last 7 days)
┌─────────────────┬───────────┬───────┬────────┬────────────────┐
│ Algorithm       │ Total Recs│ CTR % │ Like % │ Engagement %   │
├─────────────────┼───────────┼───────┼────────┼────────────────┤
│ trending_hot    │ 45        │ 15.6% │ 8.9%   │ 24.5%          │
│ content_based   │ 32        │ 18.8% │ 12.5%  │ 31.3%          │
│ hybrid          │ 28        │ 21.4% │ 10.7%  │ 32.1%          │
│ auto           │ 38        │ 17.1% │ 9.2%   │ 26.3%          │
└─────────────────┴───────────┴───────┴────────┴────────────────┘
```

### **Recommendation History**
```
📊 Recommendation History (Last 7 days)
┌─────────┬────────────┬──────────────────┬─────────────┬───────┬─────────┐
│ Time    │ User       │ Content          │ Algorithm   │ Score │ Outcome │
├─────────┼────────────┼──────────────────┼─────────────┼───────┼─────────┤
│ 01-23   │ Test User  │ Python ML Guide  │ hybrid      │ 0.856 │ clicked │
│ 01-23   │ Test User  │ React Tutorial   │ content_bas │ 0.734 │ liked   │
└─────────┴────────────┴──────────────────┴─────────────┴───────┴─────────┘
```

## 🔍 **Key Insights You'll Get**

### **Algorithm Effectiveness**
- **Best CTR**: Which algorithm gets the most clicks
- **Fastest**: Which algorithm generates recommendations quickest
- **Most Engaging**: Which creates the most user interactions
- **Most Diverse**: Which recommends the widest variety of content

### **Content Performance**
- **Most Recommended**: Which content appears in most recommendations
- **Best Converting**: Which content gets clicked most when recommended
- **Algorithm Preferences**: Which algorithms favor which content types

### **User Behavior**
- **Algorithm Response**: How users respond to different algorithms
- **Interaction Patterns**: Time to click, like, save patterns
- **Engagement Trends**: How engagement changes over time

## 🎛️ **Live Monitoring**

The tracker includes a **live monitoring mode** that updates every 5 seconds:

```bash
python recommendation_tracker.py
# Choose option 6: "Live Performance Monitor"
```

This shows real-time:
- New recommendations being generated
- User interactions happening
- Algorithm performance changes
- System responsiveness

## 📊 **Database Schema**

The tracking system uses two main tables:

### **`recommendation_logs`**
Stores every recommendation event:
- User, content, algorithm, score, position
- User outcomes (clicked, liked, saved, dismissed)
- Timing and performance metrics
- A/B testing data

### **`algorithm_performance_metrics`**
Aggregated performance snapshots:
- Hourly/daily/weekly summaries
- CTR, engagement rates, response times
- Coverage and diversity metrics

## 🔧 **Advanced Usage**

### **Filter by Algorithm**
```bash
# See only trending algorithm performance
curl "http://localhost:8000/api/v1/analytics/algorithms/performance?algorithm=trending_hot"
```

### **Track Specific Content**
```bash
# See how content ID 5 gets recommended
curl "http://localhost:8000/api/v1/analytics/content/5/recommendations"
```

### **User Journey Analysis**
```bash
# See what algorithms recommend to user 3
curl "http://localhost:8000/api/v1/analytics/users/3/recommendations"
```

## 🚀 **Next Steps**

1. **Generate Test Data**: Use the tracker to create sample recommendations
2. **Monitor Performance**: Watch live algorithm performance
3. **Optimize Algorithms**: Use insights to improve recommendation quality
4. **A/B Test**: Compare different algorithms with real users
5. **Business Intelligence**: Export data for deeper analysis

## 🎉 **Benefits**

✅ **Data-Driven Optimization** - See which algorithms actually work  
✅ **User Experience Insights** - Understand user preferences  
✅ **Performance Monitoring** - Track system speed and reliability  
✅ **Business Metrics** - Measure engagement and conversion  
✅ **Algorithm Debugging** - Identify issues and improvements  

Your recommendation system is now **fully observable** - you can see exactly what's working, what isn't, and why! 🔍✨
