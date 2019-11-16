'''
A translation function for contour data
'''

def filterTags(attrs):
    if not attrs:
        return
    
    tags={}
    
    if 'height' in attrs:
        tags['ele'] = attrs['height']
        tags['contour'] = 'elevation'
        
        height = int(attrs['height'])
        if height % 500 == 0:
            tags['contour_ext'] = 'elevation_major'
        elif height % 100 == 0:
            tags['contour_ext'] = 'elevation_medium'
        else:
            tags['contour_ext'] = 'elevation_minor'
    
    return tags

