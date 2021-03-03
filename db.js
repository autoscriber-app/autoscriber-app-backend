var mysql = require('mysql');


/** 
 * SQL SCHEMA (blobs) -> compile to jobs
 * uuid    message    time    processed
 */


/**
 * TODO:Create table with the schema ( table is for storing ML )
 * uuid          procssedMessage
 * 
 * TODO: when new procssed comes delete old
 * TODO:Grant user permission for new table
 */
var con = mysql.createConnection({
  host: "localhost",
  user: "yourusername",
  password: "yourpassword"
});

/**
 * Adds Blobs to database for later jobs
 * @param {String} uuid 
 * @param {String} message 
 * @param {Int} timestamp 
 */
function addBlob(uuid, message, timestamp) {

}

/**
 * Returns a list object sof
 * uuid : [blob1, blob2, blob3]
 */
function giveJob(uuid) {

}
/**
 * gets correct prossesed message from uuid.
 * @param {string} uuid
 * @returns {String} message 
 */
function getFinished (uuid) {

}