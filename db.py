"""
db heroku_72ea7ac5f998832
mysql://b3333c6f779dde:b10bfad4@us-cdbr-iron-east-04.cleardb.net/heroku_72ea7ac5f998832?reconnect=true

CREATE TABLE IF NOT EXISTS users (
  id INT(11) NOT NULL AUTO_INCREMENT,
  facebook_user_id INT(11) NOT NULL,
  first_name VARCHAR(45) DEFAULT NULL,
  last_name VARCHAR(45) DEFAULT NULL,
  profile_pic VARCHAR(200) DEFAULT NULL,
  locale VARCHAR(45) DEFAULT NULL,
  timezone VARCHAR(10) DEFAULT NULL,
  gender VARCHAR(10) DEFAULT NULL,
  last_seen TIMESTAMP DEFAULT NULL,
  PRIMARY KEY (id)
)

CREATE TABLE IF NOT EXISTS subscriptions (
  id INT(11) NOT NULL AUTO_INCREMENT,
  facebook_user_id INT(11) NOT NULL,
  keyword VARCHAR(45) DEFAULT NULL,
  updated_at TIMESTAMP DEFAULT NULL,
  PRIMARY KEY (id)
)
"""