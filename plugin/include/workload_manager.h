#ifndef WORKLOAD_MANAGER_H
#define WORKLOAD_MANAGER_H

#include "CGSim.h"
#include <fstream>
#include <nlohmann/json.hpp>
using json = nlohmann::json;



class WORKLOAD_MANAGER {

public:
    WORKLOAD_MANAGER(){};
   ~WORKLOAD_MANAGER(){};
    JobQueue getWorkload();
   
};


#endif //WORKLOAD_MANAGER_H
