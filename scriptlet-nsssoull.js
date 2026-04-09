/**
 * @NApiVersion 2.1
 * @NScriptType Restlet
 */
define(['N/search', 'N/record', 'N/log', 'N/runtime'], function(search, record, log, runtime) {

    /**
     * Checks permissions for the current user on a search
     * @param {string} searchId - The search ID to check
     * @returns {Object} - Permission information
     */
    /**
     * Checks permissions for the current user on a search
     * @param {string} searchId - The search ID to check
     * @returns {Object} - Permission information
     */
    const checkSearchPermissions = (searchId) => {
        try {
            log.debug("Checking search permissions", {searchId: searchId});
            
            const currentUser = runtime.getCurrentUser();
            log.debug("Current user", {
                id: currentUser.id,
                name: currentUser.name,
                role: currentUser.role
            });
            
            // Try to find the search and check if it's public or the user has proper permissions
            const searchLookup = search.create({
                type: 'savedsearch',
                filters: [
                    ['internalid', 'is', searchId],
                    'AND',
                    [
                        ['owner', 'is', currentUser.id],
                        'OR',
                        ['access', 'is', 'PUBLIC']
                    ]
                ],
                columns: ['id', 'title', 'recordtype', 'owner', 'access']
            }).run().getRange(0, 1);
            
            if (searchLookup && searchLookup.length > 0) {
                const searchInfo = {
                    id: searchLookup[0].id,
                    title: searchLookup[0].getValue('title'),
                    recordtype: searchLookup[0].getValue('recordtype'),
                    owner: searchLookup[0].getValue('owner'),
                    access: searchLookup[0].getValue('access')
                };
                
                log.debug("Search found with proper access", searchInfo);
                return {
                    hasAccess: true,
                    info: searchInfo
                };
            } else {
                // Check if the search exists at all
                const searchExists = search.create({
                    type: 'savedsearch',
                    filters: [
                        ['internalid', 'is', searchId]
                    ],
                    columns: ['id', 'title']
                }).run().getRange(0, 1);
                
                if (searchExists && searchExists.length > 0) {
                    log.debug("Search exists but user lacks permission", {
                        id: searchExists[0].id,
                        title: searchExists[0].getValue('title')
                    });
                    
                    return {
                        hasAccess: false,
                        exists: true,
                        info: {
                            id: searchExists[0].id,
                            title: searchExists[0].getValue('title')
                        }
                    };
                } else {
                    log.debug("Search does not exist", {searchId: searchId});
                    return {
                        hasAccess: false,
                        exists: false
                    };
                }
            }
        } catch (error) {
            log.error("Error checking search permissions", {
                searchId: searchId,
                error: error.message
            });
            
            return {
                hasAccess: false,
                error: error.message
            };
        }
    };
    
    /**
     * Executes a search and formats the results
     * @param {Object} searchObj - The search object to execute
     * @param {string} resultType - The type of result format ('object' or 'array')
     * @returns {Array} - The formatted search results
     */
    const searchJS = (searchObj, resultType) => {
        let results = [];
        
        if (!resultType) {
            resultType = "object";
        } else if (typeof(resultType) === "string") {
            resultType = resultType.toLowerCase();
        }
        
        log.debug("Executing search", {
            searchType: searchObj.searchType,
            resultType: resultType
        });
        
        const myPagedData = searchObj.runPaged();
        const searchResultCount = myPagedData.count;
        log.audit("searchJS result count", searchResultCount);
        
        if (searchResultCount > 4000) {
            log.debug("Search results exceed 4000, using paged search");
            myPagedData.pageRanges.forEach(function(pageRange) {
                const myPage = myPagedData.fetch({index: pageRange.index});
                log.debug("Processing page", {pageIndex: pageRange.index, pageSize: myPage.data.length});
                
                myPage.data.forEach(function(result) {
                    const all_values = result.getAllValues();
                    all_values.result_id = result.id;
                    all_values.result_type = result.recordType;
                    results.push(all_values);
                    return true;
                });
            });
        } else {
            log.debug("Search results under 4000, using standard search");
            searchObj.run().each(function(result) {
                const all_values = result.getAllValues();
                all_values.result_id = result.id;
                all_values.result_type = result.recordType;
                results.push(all_values);
                return true;
            });
        }
        
        if (resultType === "array") {
            log.debug("Converting results to array format");
            results = results.reduce((result, el) => {
                return [
                    ...result,
                    el.internalid && el.internalid[0] ? el.internalid[0].value : null,
                ];
            }, []);
        }
        
        log.debug("Search completed", {resultCount: results.length});
        return results;
    };

    /**
     * Parses a record and extracts all its field values and sublist values
     * @param {Object} objRecord - The record to parse
     * @param {boolean} is_subrecord - Whether this is a subrecord
     * @returns {Object} - The parsed record data
     */
    const parse_record = (objRecord, is_subrecord) => {
        try {
            log.debug("Parsing record", {
                type: objRecord.type,
                id: objRecord.id,
                is_subrecord: !!is_subrecord
            });
            
            const get_values = (fields_arr, sublist_id, i) => {
                const output_obj = {};
                for (const field_id of fields_arr) {
                    try {
                        let objField = {};
                        if (sublist_id) {
                            objField = objRecord.getSublistFields({
                                sublistId: sublist_id
                            });
                        } else {
                            try {
                                objField = objRecord.getField({
                                    fieldId: field_id
                                });
                            } catch (fieldErr) {
                                // Some fields might not be available through getField
                                log.debug("Field not available via getField", {
                                    fieldId: field_id,
                                    error: fieldErr.message
                                });
                                objField = null;
                            }
                        }
                        
                        const is_subrecord = objField?.type === "summary";
                        if (is_subrecord) {
                            if (sublist_id) {
                                const hasSubrecord = objRecord.hasSublistSubrecord({
                                    sublistId: sublist_id,
                                    fieldId: field_id,
                                    line: i
                                });
                                
                                if (hasSubrecord) {
                                    log.debug("Processing sublist subrecord", {
                                        sublistId: sublist_id,
                                        fieldId: field_id,
                                        line: i
                                    });
                                    
                                    const objSubRecord = objRecord.getSublistSubrecord({
                                        sublistId: sublist_id,
                                        fieldId: field_id,
                                        line: i
                                    });
                                    output_obj[field_id] = parse_record(objSubRecord, true);
                                }
                            } else {
                                const hasSubrecord = objRecord.hasSubrecord({
                                    fieldId: field_id
                                });
                                
                                if (hasSubrecord) {
                                    log.debug("Processing body subrecord", {fieldId: field_id});
                                    const objSubRecord = objRecord.getSubrecord({
                                        fieldId: field_id
                                    });
                                    output_obj[field_id] = parse_record(objSubRecord, true);
                                }
                            }
                        } else {
                            if (sublist_id) {
                                try {
                                    output_obj[field_id] = objRecord.getSublistValue({
                                        sublistId: sublist_id,
                                        fieldId: field_id,
                                        line: i
                                    });
                                } catch (sublistErr) {
                                    log.debug("Error getting sublist value", {
                                        sublistId: sublist_id,
                                        fieldId: field_id,
                                        line: i,
                                        error: sublistErr.message
                                    });
                                    output_obj[field_id] = null;
                                }
                            } else {
                                try {
                                    output_obj[field_id] = objRecord.getValue(field_id);
                                } catch (valueErr) {
                                    log.debug("Error getting field value", {
                                        fieldId: field_id,
                                        error: valueErr.message
                                    });
                                    output_obj[field_id] = null;
                                }
                            }
                        }
                    } catch (fieldProcessErr) {
                        log.error("Error processing field", {
                            fieldId: field_id,
                            sublistId: sublist_id,
                            line: i,
                            error: fieldProcessErr.message
                        });
                        output_obj[field_id] = null;
                    }
                }
                return output_obj;
            };
            
            const fields_list = objRecord.getFields();
            
            // Add mainaddress field if it's not already in the list
            if (fields_list.indexOf("mainaddress") === -1) {
                fields_list.push("mainaddress");
            }
            
            const sublist_list = objRecord.getSublists();
            const output_obj = get_values(fields_list);
            
            log.debug("Processing record sublists", {
                recordType: objRecord.type,
                recordId: objRecord.id,
                sublists: sublist_list
            });
            
            for (const sublist_id of sublist_list) {
                try {
                    output_obj[sublist_id] = [];
                    const sublist_fields = objRecord.getSublistFields({
                        sublistId: sublist_id
                    });
                    
                    const numLines = objRecord.getLineCount({
                        sublistId: sublist_id
                    });
                    
                    log.debug("Processing sublist", {
                        sublistId: sublist_id,
                        lineCount: numLines,
                        fieldCount: sublist_fields.length
                    });
                    
                    for (let i = 0; i < numLines; i++) {
                        output_obj[sublist_id].push(get_values(sublist_fields, sublist_id, i));
                    }
                } catch (sublistErr) {
                    log.error("Error processing sublist", {
                        sublistId: sublist_id,
                        error: sublistErr.message
                    });
                    output_obj[sublist_id] = [];
                }
            }
            
            return output_obj;
        } catch (parseErr) {
            log.error("Error in parse_record", {
                recordType: objRecord ? objRecord.type : 'unknown',
                recordId: objRecord ? objRecord.id : 'unknown',
                error: parseErr.message,
                stack: parseErr.stack
            });
            throw parseErr;
        }
    };

    /**
     * Parses a record based on input parameters
     * @param {Object} input_obj - The input parameters
     * @returns {Object} - The parsed record data
     */
    const parse = (input_obj) => {
        try {
            log.debug("parse function called with input", input_obj);
            
            // Handle saved search case
            if (input_obj.savedSearchId) {
                log.debug("Processing saved search", {searchId: input_obj.savedSearchId});
                
                try {
                    // Load the saved search with more robust error handling
                    let savedSearch;
                    try {
                        savedSearch = search.load({
                            id: input_obj.savedSearchId
                        });
                        
                        log.debug("Saved search loaded", {
                            id: input_obj.savedSearchId,
                            type: savedSearch.searchType
                        });
                    } catch (loadError) {
                        // Try alternate methods to find the search
                        log.warning("Failed to load saved search directly", {
                            searchId: input_obj.savedSearchId,
                            error: loadError.message
                        });
                        
                        // Attempt to find the search via search API
                        try {
                            const searchResults = search.create({
                                type: 'savedsearch',
                                filters: [
                                    ['internalid', 'is', input_obj.savedSearchId]
                                ],
                                columns: ['id', 'title', 'recordtype']
                            }).run().getRange(0, 1);
                            
                            if (searchResults && searchResults.length > 0) {
                                const searchInfo = {
                                    id: searchResults[0].id,
                                    title: searchResults[0].getValue('title'),
                                    recordtype: searchResults[0].getValue('recordtype')
                                };
                                
                                log.debug("Found saved search via search API", searchInfo);
                                
                                // Try loading again with the confirmed ID
                                savedSearch = search.load({
                                    id: searchInfo.id
                                });
                            } else {
                                throw new Error("Saved search not found via search API");
                            }
                        } catch (alternateError) {
                            log.error("All attempts to find saved search failed", {
                                searchId: input_obj.savedSearchId,
                                directError: loadError.message,
                                searchApiError: alternateError.message
                            });
                            
                            throw new Error(`Saved search ${input_obj.savedSearchId} not found or not accessible. Verify the ID and permissions.`);
                        }
                    }
                    
                    // Run the search and get results
                    return searchJS(savedSearch, input_obj.resultType || "object");
                } catch (searchErr) {
                    log.error("Error loading or running saved search", {
                        searchId: input_obj.savedSearchId,
                        error: searchErr.message,
                        stack: searchErr.stack
                    });
                    throw new Error(`Saved search processing error: ${searchErr.message}`);
                }
            }
            
            // Handle search from filters/columns case
            if (input_obj.type && (input_obj.filters || input_obj.columns)) {
                log.debug("Creating search from parameters", {
                    type: input_obj.type,
                    hasFilters: !!input_obj.filters,
                    hasColumns: !!input_obj.columns
                });
                
                let filters = input_obj.filters;
                let columns = input_obj.columns;
                
                // Parse JSON strings if needed
                if (typeof filters === 'string') {
                    try {
                        filters = JSON.parse(filters);
                    } catch (parseError) {
                        log.error("Error parsing filters JSON", {
                            filters: input_obj.filters,
                            error: parseError.message
                        });
                        throw new Error(`Invalid filters JSON: ${parseError.message}`);
                    }
                }
                
                if (typeof columns === 'string') {
                    try {
                        columns = JSON.parse(columns);
                    } catch (parseError) {
                        log.error("Error parsing columns JSON", {
                            columns: input_obj.columns,
                            error: parseError.message
                        });
                        throw new Error(`Invalid columns JSON: ${parseError.message}`);
                    }
                }
                
                // Default to just internalid if no columns specified
                if (!columns || columns.length === 0) {
                    columns = ["internalid"];
                }
                
                try {
                    const searchObj = search.create({
                        type: input_obj.type,
                        filters: filters,
                        columns: columns
                    });
                    
                    const searchResultCount = searchObj.runPaged().count;
                    log.debug("Search created and executed", {
                        type: input_obj.type,
                        resultCount: searchResultCount
                    });
                    
                    if (searchResultCount === 0) {
                        log.warning(`No results found for ${input_obj.type}`, {
                            filters: filters
                        });
                        return [];
                    }
                    
                    // If we need to load a record by ID (not just search results)
                    if (input_obj.loadRecord === true) {
                        if (!input_obj.id) {
                            // Extract ID from search if not provided
                            searchObj.run().each(function(result) {
                                input_obj.id = result.getValue("internalid");
                                return false; // Only get the first result
                            });
                        }
                        
                        if (!input_obj.id) {
                            throw new Error(`No record ID found for ${input_obj.type}`);
                        }
                        
                        log.debug("Loading record from search results", {
                            type: input_obj.type,
                            id: input_obj.id
                        });
                        
                        const objRecord = record.load({
                            type: input_obj.type,
                            id: input_obj.id
                        });
                        
                        return parse_record(objRecord);
                    }
                    
                    // Return search results if not loading full record
                    return searchJS(searchObj, input_obj.resultType || "object");
                } catch (searchCreateErr) {
                    log.error("Error creating or running search", {
                        type: input_obj.type,
                        error: searchCreateErr.message,
                        stack: searchCreateErr.stack
                    });
                    throw searchCreateErr;
                }
            }
            
            // Handle direct record load case
            if (input_obj.type && input_obj.id) {
                log.debug("Loading record directly", {
                    type: input_obj.type,
                    id: input_obj.id
                });
                
                try {
                    const objRecord = record.load({
                        type: input_obj.type,
                        id: input_obj.id
                    });
                    
                    return parse_record(objRecord);
                } catch (loadErr) {
                    log.error("Error loading record", {
                        type: input_obj.type,
                        id: input_obj.id,
                        error: loadErr.message,
                        stack: loadErr.stack
                    });
                    throw loadErr;
                }
            }
            
            log.error("Invalid input parameters", input_obj);
            throw new Error("Invalid input parameters. Must provide either savedSearchId, type+filters, or type+id.");
        } catch (parseErr) {
            log.error("Error in parse function", {
                error: parseErr.message,
                stack: parseErr.stack,
                input: JSON.stringify(input_obj)
            });
            throw parseErr;
        }
    };

    /**
     * Handles GET requests to the RESTlet
     * @param {Object} context - The request context
     * @returns {string} - The JSON response
     */
    function handleGet(context) {
        try {
            log.audit("RESTlet GET request received", context);
            
            // Check for required parameters
            const searchId = context.searchid;
            if (!searchId) {
                log.error("Missing required parameter", {parameter: "searchid"});
                return JSON.stringify({
                    success: false,
                    error: "Missing required parameter",
                    details: "searchid parameter is required"
                });
            }
            
            log.debug("Processing saved search request", {searchId: searchId});
            
            // Handle different ways the search ID might be provided
            let normalizedSearchId = searchId;
            
            // If the ID is numeric but presented as a string, ensure it's treated as a numeric ID
            if (!isNaN(searchId) && typeof searchId === 'string') {
                normalizedSearchId = parseInt(searchId, 10);
                log.debug("Normalized search ID", {
                    original: searchId,
                    normalized: normalizedSearchId
                });
            }
            
            // Check if ID includes "customsearch" prefix - handle both formats
            const customSearchMatch = String(searchId).match(/^customsearch(_|-|)(\d+)$/i);
            if (customSearchMatch) {
                normalizedSearchId = customSearchMatch[2];
                log.debug("Extracted numeric ID from customsearch format", {
                    original: searchId,
                    normalized: normalizedSearchId
                });
            }
            
            // Try alternative approaches if search ID issues persist
            const searchMethods = [
                {
                    name: "Direct numeric ID",
                    input: {
                        savedSearchId: normalizedSearchId,
                        resultType: context.resulttype || "object"
                    }
                },
                {
                    name: "CustomSearch prefix",
                    input: {
                        savedSearchId: "customsearch_" + normalizedSearchId,
                        resultType: context.resulttype || "object"
                    }
                },
                {
                    name: "CustomSearch with dash",
                    input: {
                        savedSearchId: "customsearch-" + normalizedSearchId,
                        resultType: context.resulttype || "object"
                    }
                }
            ];
            
            // Check if search exists and permissions
            const permissionCheck = checkSearchPermissions(normalizedSearchId);
            log.debug("Permission check results", permissionCheck);
            
            if (permissionCheck.exists === false) {
                // Also try with customsearch prefix
                const prefixPermCheck = checkSearchPermissions("customsearch_" + normalizedSearchId);
                
                if (prefixPermCheck.exists) {
                    log.debug("Search found with customsearch_ prefix", prefixPermCheck);
                    
                    if (!prefixPermCheck.hasAccess) {
                        return JSON.stringify({
                            success: false,
                            error: "Permission denied",
                            details: `User does not have permission to access saved search customsearch_${normalizedSearchId}`,
                            searchInfo: prefixPermCheck.info || null
                        });
                    }
                }
                
                // Try with dash as well
                const dashPermCheck = checkSearchPermissions("customsearch-" + normalizedSearchId);
                if (dashPermCheck.exists) {
                    log.debug("Search found with customsearch- prefix", dashPermCheck);
                    
                    if (!dashPermCheck.hasAccess) {
                        return JSON.stringify({
                            success: false,
                            error: "Permission denied",
                            details: `User does not have permission to access saved search customsearch-${normalizedSearchId}`,
                            searchInfo: dashPermCheck.info || null
                        });
                    }
                }
            } else if (permissionCheck.exists && !permissionCheck.hasAccess) {
                return JSON.stringify({
                    success: false,
                    error: "Permission denied",
                    details: `User does not have permission to access saved search ${normalizedSearchId}`,
                    searchInfo: permissionCheck.info || null
                });
            }
            
            // If record type is provided, add it to the search context
            if (context.recordtype) {
                log.debug("Record type provided", {recordType: context.recordtype});
                
                // Add a search method using standard search instead of saved search
                searchMethods.push({
                    name: "Standard search by type",
                    input: {
                        type: context.recordtype,
                        filters: "[]",
                        columns: "[]",
                        resultType: context.resulttype || "object"
                    }
                });
            }
            
            // Try each method until one works
            let lastError = null;
            for (const method of searchMethods) {
                try {
                    log.debug(`Trying search method: ${method.name}`, method.input);
                    const searchResults = parse(method.input);
                    
                    log.debug("Search completed successfully", {
                        method: method.name,
                        resultCount: Array.isArray(searchResults) ? searchResults.length : 'N/A'
                    });
                    
                    return JSON.stringify({
                        success: true,
                        data: searchResults,
                        method: method.name
                    });
                } catch (methodError) {
                    log.warning(`Search method failed: ${method.name}`, {
                        error: methodError.message
                    });
                    lastError = methodError;
                    // Continue to the next method
                }
            }
            
            // If we got here, all methods failed
            log.error("All search methods failed", {
                searchId: searchId,
                normalizedId: normalizedSearchId,
                lastError: lastError.message
            });
            
            return JSON.stringify({
                success: false,
                error: "Error processing saved search",
                details: lastError.message,
                suggestions: [
                    "Verify the saved search ID is correct",
                    "Ensure the current user has permission to access this saved search",
                    "Try providing the 'recordtype' parameter if you know the record type",
                    "Check if the saved search still exists in NetSuite"
                ]
            });
        } catch (error) {
            log.error("Unhandled error in handleGet", {
                error: error.message,
                stack: error.stack,
                context: JSON.stringify(context)
            });
            
            return JSON.stringify({
                success: false,
                error: "An error occurred while processing your request. See details in NetSuite script logs.",
                details: error.message
            });
        }
    }

    return {
        get: handleGet
    };
});