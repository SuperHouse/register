# Testomatic Circuit Board Register

This Register provides a central location for storing production and testing 
data related to printed circuit board assembly (PCBA) services. It was 
created for storing data produced by the [Testomatic](https://github.com/superhouse/testomatic) 
PCB test jig system, but it doesn't require Testomatic to operate. You can 
use this Register independently, even without a PCB testing system at all. Its 
job is simply to store and report information about individual PCBs 
regardless of how the data is obtained.

It includes:

 * A database for storage of information relating to individual boards
 * Image storage to associate images with test records or boards
 * An internal web UI for managing records of boards and tests
 * An external web UI for customers to look up details of specific boards
 * An API for updating data stored in the system
 * Supporting scripts to process photos of PCBs, extract serial numbers from barcodes, and store them

Data is stored in a hierarchical manner:

**Organisations** can represent customers such as companies that have 
purchased or commissioned the assembly of boards.

**Users** have access to the system through a username and password, and 
are associated with one or more organisations.

**Designs** represent a type of circuit board, and are associated with an 
organisation.

**Boards** represent individual circuit boards with a serial number 
assigned, which are an embodiment of a design.

![](images/register-device-details.png)

It's written as a Django + React application and can use either SQLite 
or MariaDB / MySQL.