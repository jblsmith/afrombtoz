#!/usr/bin/env python
# encoding: utf=8

"""
afrombtoz.py

Re-synthesize song A using the segments of songs B to Z.

This is the same as afromb.py by Ben Lacker (2009-02-24),
except it allows multiple source files instead of just one.

By Jordan B. L. Smith, 2015
"""

import numpy
import sys
import time
import echonest.remix.audio as audio
import argparse
    
usage="""
Example:
    python afrombtoz.py A.mp3 B.mp3 C.mp3 D.mp3 -o output.mp3 -m 0.8

This will attempt to recreate A (the target) from B, C and D (the sources).

The 'env' flag applies the volume envelopes of the segments of A to those
from B.

Mix (-m) is a number 0-1 that determines the relative mix of the resynthesized
(wet) output. If m = 0.8, the mix will be mostly resynthesized.
"""

class AfromB(object):
    def __init__(self, target_filename, input_filenames_bz, output_filename):
        self.target = audio.LocalAudioFile(target_filename)
        self.target_segs = self.target.analysis.segments
        self.sources = []
        self.source_segs = []
        for filename in input_filenames_bz:
            self.sources.append(audio.LocalAudioFile(filename))
            self.source_segs.append(self.sources[-1].analysis.segments)
        
        self.output_filename = output_filename


    def calculate_distances(self, a, segs):
        distance_matrix = numpy.zeros((len(segs), 4),
                                        dtype=numpy.float32)
        pitch_distances = []
        timbre_distances = []
        loudmax_distances = []
        # We call these 'b's but whether they are 'b's or 'c's now depends on what SEGS are passed!
        for b in segs:
            pitch_diff = numpy.subtract(b.pitches,a.pitches)
            pitch_distances.append(numpy.sum(numpy.square(pitch_diff)))
            timbre_diff = numpy.subtract(b.timbre,a.timbre)
            timbre_distances.append(numpy.sum(numpy.square(timbre_diff)))
            loudmax_diff = b.loudness_begin - a.loudness_begin
            loudmax_distances.append(numpy.square(loudmax_diff))
        distance_matrix[:,0] = pitch_distances
        distance_matrix[:,1] = timbre_distances
        distance_matrix[:,2] = loudmax_distances
        distance_matrix[:,3] = range(len(segs))
        distance_matrix = self.normalize_distance_matrix(distance_matrix)
        return distance_matrix

    def normalize_distance_matrix(self, mat, mode='minmed'):
        """ Normalize a distance matrix on a per column basis.
        """
        if mode == 'minstd':
            mini = numpy.min(mat,0)
            m = numpy.subtract(mat, mini)
            std = numpy.std(mat,0)
            m = numpy.divide(m, std)
            m = numpy.divide(m, mat.shape[1])
        elif mode == 'minmed':
            mini = numpy.min(mat,0)
            m = numpy.subtract(mat, mini)
            med = numpy.median(m)
            m = numpy.divide(m, med)
            m = numpy.divide(m, mat.shape[1])
        elif mode == 'std':
            std = numpy.std(mat,0)
            m = numpy.divide(mat, std)
            m = numpy.divide(m, mat.shape[1])
        return m

    def run(self, mix=0.5, envelope=False):
        dur = len(self.target.data) + 100000 # another two seconds
        # determine shape of new array
        if len(self.target.data.shape) > 1:
            new_shape = (dur, self.target.data.shape[1])
            new_channels = self.target.data.shape[1]
        else:
            new_shape = (dur,)
            new_channels = 1
        out = audio.AudioData(shape=new_shape,
                            sampleRate=self.sources[0].sampleRate,
                            numChannels=new_channels)
        for a in self.target_segs:
            seg_index = a.absolute_context()[0]
            distance_matrices = [self.calculate_distances(a,segs_i) for segs_i in self.source_segs]
            distances_fromi = [[numpy.sqrt(x[0]+x[1]+x[2]) for x in distance_matrix_atoi] for distance_matrix_atoi in distance_matrices]
            minima = [(min(dists), dists.index(min(dists))) for dists in distances_fromi]
            segopts_index = minima.index(min(minima))
            seg_index = minima[segopts_index][1]
            match = self.source_segs[segopts_index][distances_fromi[segopts_index].index(minima[segopts_index][0])]
            segment_data = self.sources[segopts_index][match]
            reference_data = self.target[a]
            if segment_data.endindex < reference_data.endindex:
                if new_channels > 1:
                    silence_shape = (reference_data.endindex,new_channels)
                else:
                    silence_shape = (reference_data.endindex,)
                new_segment = audio.AudioData(shape=silence_shape,
                                        sampleRate=out.sampleRate,
                                        numChannels=segment_data.numChannels)
                new_segment.append(segment_data)
                new_segment.endindex = len(new_segment)
                segment_data = new_segment
            elif segment_data.endindex > reference_data.endindex:
                index = slice(0, int(reference_data.endindex), 1)
                segment_data = audio.AudioData(None,segment_data.data[index],
                                        sampleRate=segment_data.sampleRate)
            if envelope:
                # db -> voltage ratio http://www.mogami.com/e/cad/db.html
                linear_max_volume = pow(10.0,a.loudness_max/20.0)
                linear_start_volume = pow(10.0,a.loudness_begin/20.0)
                if(seg_index == len(self.target_segs)-1): # if this is the last segment
                    linear_next_start_volume = 0
                else:
                    linear_next_start_volume = pow(10.0,self.target_segs[seg_index+1].loudness_begin/20.0)
                    pass
                when_max_volume = a.time_loudness_max
                # Count # of ticks I wait doing volume ramp so I can fix up rounding errors later.
                ss = 0
                # Set volume of this segment. Start at the start volume, ramp up to the max volume , then ramp back down to the next start volume.
                cur_vol = float(linear_start_volume)
                # Do the ramp up to max from start
                samps_to_max_loudness_from_here = int(segment_data.sampleRate * when_max_volume)
                if(samps_to_max_loudness_from_here > 0):
                    how_much_volume_to_increase_per_samp = float(linear_max_volume - linear_start_volume)/float(samps_to_max_loudness_from_here)
                    for samps in xrange(samps_to_max_loudness_from_here):
                        try:
                            segment_data.data[ss] *= cur_vol
                        except IndexError:
                            pass
                        cur_vol = cur_vol + how_much_volume_to_increase_per_samp
                        ss = ss + 1
                # Now ramp down from max to start of next seg
                samps_to_next_segment_from_here = int(segment_data.sampleRate * (a.duration-when_max_volume))
                if(samps_to_next_segment_from_here > 0):
                    how_much_volume_to_decrease_per_samp = float(linear_max_volume - linear_next_start_volume)/float(samps_to_next_segment_from_here)
                    for samps in xrange(samps_to_next_segment_from_here):
                        cur_vol = cur_vol - how_much_volume_to_decrease_per_samp
                        try:
                            segment_data.data[ss] *= cur_vol
                        except IndexError:
                            pass
                        ss = ss + 1
            mixed_data = audio.mix(segment_data,reference_data,mix=mix)
            out.append(mixed_data)
        out.encode(self.output_filename)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('target', help='Target file to reconstruct')
    parser.add_argument('sources',nargs='+',default=["Song A","Song B"], type=str, help='Source files to use for reconstruction (list as many as you like)')
    parser.add_argument('-o','--output_file', help='Output file (default: tmp.mp3)', default="tmp.mp3", required=False, type=str)
    parser.add_argument('-m','--mix', help='Mixing level (default is 1, all wet)', default=1, required=False, type=float)
    parser.add_argument('-s','--scale', help='Hierarchical scale at which to remix elements', default='segments', required=False, type=str)
    parser.add_argument('--env', help='Flag to use enveloping', action='store_true', required=False)
    try:
        args = parser.parse_args()
        print args
    except:
        print usage
        sys.exit(-1)
    
    AfromB(args.target, args.sources, args.output_file).run(mix=args.mix,
                                                                envelope=args.env)

if __name__=='__main__':
    tic = time.time()
    main()
    toc = time.time()
    print "Elapsed time: %.3f sec" % float(toc-tic)