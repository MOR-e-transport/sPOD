#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 29 09:19:19 2018

@author: Philipp Krah

This package provides all the infrastructure for the 
    
    shifted propper orthogonal decomposition (SPOD)

"""
############################
# import MODULES here:
############################
import pickle

import numpy as np
import matplotlib.pyplot as plt
from numpy import exp, meshgrid, mod,size, interp, where, diag, reshape, \
                    asarray
from sklearn.utils.extmath import randomized_svd
from numpy.linalg import lstsq, norm, svd
#from scipy.linalg import svd
import os
import time
from matplotlib.pyplot import   subplot, plot, pcolor, semilogy, title, \
                                xlabel, ylabel, figure
from warnings import warn
###############################
# sPOD general SETTINGS:
###############################
# %%
###############################################################################
# CLASS of CO MOVING FRAMES
###############################################################################                                
class frame:
    # TODO: Add properties of class frame in the description
    """ Definition is physics motivated: 
        All points are in a inertial system (frame), if they can be transformed to 
        the rest frame by a galilei transform.
        The frame is represented by an orthogonal system.
    """

    def __init__(self, transform=None, field=None, number_of_modes=None, fname = None):
        """
        Initialize a co moving frame.
        """
        if fname:
            self.load(fname)
            self.Nmodes = np.sum(self.modal_system["sigma"] > 0)
        else:
            data_shape = transform.data_shape
            self.data_shape = data_shape
            self.Ngrid = np.prod(data_shape[:3])
            self.Ntime = data_shape[3]
            self.trafo = transform
            self.dim = self.trafo.dim
            #if not number_of_modes:
             #   self.Nmodes = self.Ntime
            #else:
            #    self.Nmodes = number_of_modes
            self.Nmodes = number_of_modes
            # transform the field to reference frame
            if not np.all(field == None):
                field = self.trafo.reverse(field)
                self.set_orthonormal_system(field)
            #print("We have initialiced a new field!")

    def save(self, fname):
        with open(fname, 'wb') as f:
            pickle.dump(self, f, pickle.HIGHEST_PROTOCOL)

    def load(self, fname):
        with open(fname, 'rb') as f:
            frame_load = pickle.load(f)
        self.__init__(frame_load.trafo)
        self.modal_system = frame_load.modal_system


    def reduce(self, field, r, use_rSVD = False):
        """
        Reduce the full filed using the first N modes of the Singular
        Value Decomposition
        """
        if use_rSVD == True:
            u, s, vt = randomized_svd(field, n_components=r)
        else:
            [U, S, VT] = svd(field, full_matrices=False)
            s = S[:r]
            u = U[:, :r]
            vt = VT[:r, :]
        
        return u, s, vt
        
    def set_orthonormal_system(self, field, use_rSVD = False):
        """
        In this routine we set the orthonormal vectors of the SVD in the 
        corresponding frames.
        """

        # reshape to snapshot matrix
        X = reshape(field, [-1, self.Ntime])
        # make an singular value decomposition of the snapshot matrix
        # and reduce it to the specified numer of moddes
        [U, S, VT] = self.reduce(X, self.Nmodes, use_rSVD)
        # the snapshot matrix is only stored with reduced number of SVD modes
        self.modal_system = {"U": U, "sigma": S, "VT": VT}

    def build_field(self, rank = None):
        """
        Calculate the field from the SVD modes: X=U*S*VT
        """
        # modes from the singular value decomposition
        u = self.modal_system["U"]
        s = self.modal_system["sigma"]
        vh = self.modal_system["VT"]
        if rank:
            u = u[:,:rank]
            s = s[:rank]
            vh = vh[:rank,:]
        # add up all the modes A=U * S * VH
        return np.dot(u * s, vh)


    def plot_singular_values(self):
        """
        This function plots the singular values of the frame.
        """
        sigmas = self.modal_system["sigma"]
        semilogy(sigmas/sigmas[0], "r+")
        xlabel(r"$i$")
        ylabel(r"$\sigma_i/\sigma_0$")

    def concatenate(self, other):
        """ Add two frames for the purpose of concatenating there modes """
        # TODO make check if other and self can be added:
        # are they in the same frame? Are they from the same data etc.
        new = frame(self.trafo,
                    self.build_field(), self.Nmodes)
        # combine left singular vecotrs
        Uself = self.modal_system["U"]
        Uother = other.modal_system["U"]
        new.modal_system["U"] = np.concatenate([Uself, Uother], axis=1)

        # combine right singular vecotrs
        VTself = self.modal_system["VT"]
        VTother = other.modal_system["VT"]
        new.modal_system["VT"] = np.concatenate([VTself, VTother], axis=0)

        Sself = self.modal_system["sigma"]
        Sother = other.modal_system["sigma"]
        new.modal_system["sigma"] = np.concatenate([Sself, Sother])

        new.Nmodes += other.Nmodes

        return new
    
    def __add__(self, other):
        """ Add two frames  """
        if isinstance(other,frame):    
            new_field = self.build_field() + other.build_field()
        elif np.shape(other)==self.data_shape:
            new_field = self.build_field() + other
        
        # apply svd and save modes
        self.set_orthonormal_system(new_field)

        return self

# %%
###############################################################################
# build frames
###############################################################################

def build_all_frames(frames, trafos = None, ranks = None):
    """
    Build up the truncated data field from the result of
     the sPOD decomposition
    :param frames: List of frames q_k , k = 1,...,F
    :param trafos: List of transformations T^k
    :param ranks: integer number r_k > 0
    :return: q = sum_k T^k q^k where q^k is of rank r_k
    """
    if trafos is None:
        trafos = [f.trafo for f in frames]

    if ranks is not None:
        if type(ranks) == int:
            ranks = [ranks]*len(trafos)
    else:
        ranks = [frame.Nmodes for frame in frames]

    qtilde = 0
    for k, (trafo, frame) in enumerate(zip(trafos, frames)):
            qtilde += trafo.apply(frame.build_field(ranks[k]))

    return qtilde


# %%
###############################################################################
# Determination of shift velocities
###############################################################################

def shift_velocities(dx, dt, fields, n_velocities, v_min, v_max, v_step, n_modes):
    sigmas = np.zeros([int((v_max-v_min)/v_step), n_modes])
    v_shifts = np.linspace(v_min, v_max, int((v_max-v_min)/v_step))

    i = 0
    for v in v_shifts:
        example_frame = frame(v, dx, dt, fields, n_modes)
        sigmas[i, :] = example_frame.modal_system["sigma"]
        i += 1

    # Plot singular value spectrum
    plt.plot(v_shifts, sigmas, 'o')

    sigmas_temp = sigmas.copy()
    c_shifts = []

    for i in range(n_velocities):
        max_index = np.where(sigmas_temp == sigmas_temp.max())
        max_index_x = max_index[0]
        max_index_x = max_index_x[0]
        max_index_y = max_index[1]
        max_index_y = max_index_y[0]

        sigmas_temp[max_index_x, max_index_y] = 0

        c_shifts.append(v_shifts[max_index_x])

    return c_shifts

###############################################################################
# Proximal operators
###############################################################################
def shrink(X, tau):
    """
    Proximal Operator for 1 norm minimization

    :param X: input matrix or vector
    :param tau: threshold
    :return: argmin_X1 tau * || X1 ||_1 + 1/2|| X1 - X||_F^2
    """
    return np.sign(X)*np.maximum(np.abs(X)-tau, 0)

def SVT(X, mu, nmodes_max = None, use_rSVD = False):
    """
    Proximal Operator for schatten 1 norm minimization
    :param X: input matrix for thresholding
    :param mu: threshold
    :return: argmin_X1 mu|| X1 ||_* + 1/2|| X1 - X||_F^2
    """
    if nmodes_max:
        if use_rSVD:
            u, s, vt = randomized_svd(X, n_components=nmodes_max)
        else:
            u, s, vt = svd(X, full_matrices=False)
            s = s[:nmodes_max]
            u = u[:, :nmodes_max]
            vt = vt[:nmodes_max, :]
    else:
        u, s, vt = svd(X, full_matrices=False)
    s = shrink(s, mu)
    return (u, s, vt)



###############################################################################
# update the Xtilde frames and truncate modes
###############################################################################

def update_and_reduce_modes(Xtilde_frames, alpha, X_coef_shift, Nmodes_reduce):

    """
    This function implements the 5. step of the SPOD algorithm (see Reiss2017)
    - calculate the new modes from the optimiced alpha combining 
    Xtilde and R modes.
    - truncate the number of modes to the desired number of reduced modes 
    - update the new Xtilde in the corresponding frames
    """
    for k, frame in enumerate(Xtilde_frames):
        Nmodes = frame.Nmodes
        alpha_k = alpha[k*Nmodes:(k+1)*Nmodes]
        # linear combination to get the new Xtilde
        Xnew_k = X_coef_shift[:, k*Nmodes:(k+1)*Nmodes] @ alpha_k
        Xnew_k = reshape(Xnew_k, [-1, frame.Ntime])
        frame.Nmodes = Nmodes_reduce  # reduce to the desired number of modes
        [U, S, VT] = frame.reduce(Xnew_k, Nmodes_reduce)
        frame.modal_system = {"U": U, "sigma": S, "VT": VT}

# %%
###############################################################################
# sPOD algorithms
###############################################################################
##############################
# CLASS of return values
##############################
class ReturnValue:
    """
    This class inherits all return values of the shifted POD routines
    """
    def __init__(self, frames, approximation, relaltive_error_hist = None, error_matrix = None, ranks = None):
     self.frames = frames               # list of all frames
     self.data_approx = approximation   # approximation of the snapshot data
     if relaltive_error_hist is not None:
        self.rel_err_hist = relaltive_error_hist
     if error_matrix is not None:
        self.error_matrix = error_matrix
     if ranks is not None:
         self.ranks = ranks

###############################################################################
# distribute the residual of frame
###############################################################################        
def shifted_POD(snapshot_matrix, transforms, nmodes, eps, Niter=1, visualize=True, use_rSVD = False):
    """
    :param snapshot_matrix: M x N matrix with N beeing the number of snapshots, M is the ODE dimension
    :param transforms: Transformations
    :param nmodes: number of modes allowed in each frame
    :param eps: stopping criteria
    :param Niter: maximal number of iterations
    :param visualize: if true: show intermediet results
    :return:
    """

    assert (np.ndim(snapshot_matrix) == 2), "Are you stephen hawking, trying to solve this problem in 16 dimensions?" \
                             "Please give me a snapshotmatrix with every snapshot in one column"
    if use_rSVD:
        warn("Using rSVD to accelarate decomposition procedure may lead to different results, pls check!")
    #########################
    ## 1.Step: Initialize
    #########################
    q = snapshot_matrix
    qtilde = np.zeros_like(q)
    Nframes = len(transforms)
    if np.size(nmodes) != Nframes:
        nmodes = list([nmodes]) * Nframes
    qtilde_frames = [frame(trafo, qtilde, number_of_modes=nmodes[k]) for k,trafo in enumerate(transforms)]
    norm_q = norm(reshape(q,-1))

    ###########################
    # error of svd:
    r_ = np.sum(nmodes)
    if use_rSVD == True:
        u, s, vt = randomized_svd(q, n_components=r_)
    else:
        [U, S, VT] = svd(q, full_matrices=False)
        s = S[:r_]
        u = U[:, :r_]
        vt = VT[:r_, :]
    err_svd = np.linalg.norm(q - np.dot(u * s, vt),ord="fro") / norm_q
    print("rel-error using svd with %d modes:%4.4e"%(r_,err_svd))
    ###########################

    it = 0
    rel_err = 1
    rel_err_list = []
    while rel_err > eps and it < Niter:

        it += 1  # counts the number of iterations in the loop
        #############################
        # 2.Step: Calculate Residual
        #############################
        res = q - qtilde
        norm_res = norm(reshape(res,-1))
        rel_err = norm_res/norm_q
        rel_err_list.append(rel_err)
        qtilde = np.zeros_like(q)

        ###########################
        # 3. Step: update frames
        ##########################
        t = time.time()
        for k, (trafo,q_frame) in enumerate(zip(transforms,qtilde_frames)):
            #R_frame = frame(trafo, res, number_of_modes=nmodes)
            res_shifted = trafo.reverse(res)
            q_frame_field = q_frame.build_field()
            q_frame.set_orthonormal_system(q_frame_field + res_shifted/Nframes, use_rSVD)
            qtilde += trafo.apply(q_frame.build_field())
        elapsed = time.time() - t
        print("it=%d rel_err= %4.4e t_cpu = %2.2f" % (it, rel_err, elapsed))

    return ReturnValue(qtilde_frames, qtilde, rel_err_list)

def give_interpolation_error(snapshot_data, trafo):
    """
    This function computes the interpolation error of the non-linear representation of the data.
    The error is "the best you can get" with the shifted POD.
    Therefore it is the smallest possible error the shifted POD decomposition allows and can be
    used as the stopping criteria inside the sPOD algorithm.
    We calculate the relative error from the Frobenius norm:

        err = || Q - T^(-1)[T[Q]] ||_F^2 / || Q ||_F^2
    :param snapshot_data:
    :param trafo:
    :return:
    """
    from numpy import reshape

    Q = reshape(snapshot_data,[-1,snapshot_data.shape[-1]])
    rel_err  = norm(Q - trafo.apply(trafo.reverse(Q)), ord="fro")/norm(Q, ord="fro")
    return rel_err/2



###############################################################################
# shifted rPCA
###############################################################################
# def shifted_rPCA_(snapshot_matrix, transforms, eps, Niter=1, visualize=True):
#     """
#     Currently this method doesnt work. Its very similar to distribute residual, but does not seem to converge
#     :param snapshot_matrix: M x N matrix with N beeing the number of snapshots
#     :param transforms: Transformations
#     :param eps: stopping criteria
#     :param Niter: maximal number of iterations
#     :param visualize: if true: show intermediet results
#     :return:
#     """
#     assert (np.ndim(snapshot_matrix) == 2), "Are you stephen hawking trying to solve this problem in 16 dimensions?" \
#                              "Please give me a snapshotmatrix with every snapshot in one column"
#     #########################
#     ## 1.Step: Initialize
#     #########################
#     qtilde = np.zeros_like(snapshot_matrix)
#     E = np.zeros_like(snapshot_matrix)
#     Y = np.zeros_like(snapshot_matrix)
#     qtilde_frames = [frame(trafo, qtilde) for trafo in transforms]
#     q = snapshot_matrix.copy()
#     norm_q = norm(reshape(q, -1))
#     it = 0
#     M, N = np.shape(q)
#     mu = M * N / (4 * np.sum(np.abs(q)))
#     lambd = 10 * 1 / np.sqrt(np.maximum(M, N))
#     thresh = 1e-7 * norm_q
#     mu_inv = 1 / mu
#     rel_err = 1
#     res = q # in the first step the residuum is q since qtilde is 0
#     while rel_err > eps and it < Niter:
#
#         it += 1  # counts the number of iterations in the loop
#         #############################
#         # 2.Step: set qtilde to 0
#         #############################
#         qtilde = np.zeros_like(q)
#         ranks = []
#         ###########################
#         # 3. Step: update frames
#         ##########################
#         t = time.time()
#         for k, (trafo, q_frame) in enumerate(zip(transforms, qtilde_frames)):
#             # R_frame = frame(trafo, res, number_of_modes=nmodes)
#             q_frame_field = q_frame.build_field()
#             res_shifted = trafo.apply(res + mu_inv * Y)
#             q_frame_field += res_shifted
#             [U, S, VT] = SVT(q_frame_field, mu_inv)
#             rank = np.sum(S > 0)
#             q_frame.modal_system = {"U": U[:,:rank], "sigma": S[:rank], "VT": VT[:rank,:]}
#             # q_frame += R_frame.build_field()/Nframes
#             qtilde += trafo.reverse(q_frame.build_field())
#    sav         ranks.append(rank) # list of ranks for each frame
#         ###########################
#         # 4. Step: update noice term
#         ##########################
#         E = shrink(q - qtilde + mu_inv * Y, lambd * mu_inv)
#         #############################
#         # 5. Step: update multiplier
#         #############################
#         res = q - qtilde - E
#         Y = Y + mu * (res)
#
#         norm_res = norm(reshape(res, -1))
#         rel_err = norm_res / norm_q
#
#         elapsed = time.time() - t
#         print("it=%d rel_err= %4.4e norm(E) = %4.1e tcpu = %2.2f, ranks_frame = " % (it, rel_err, norm(reshape(E, -1)), elapsed), *ranks)
#
#     return qtilde_frames, qtilde



###############################################################################
# shifted rPCA
###############################################################################
def shifted_rPCA(snapshot_matrix, transforms, nmodes_max=None, eps=1e-16, Niter=1, use_rSVD= False, visualize=True, mu = None, lambd = None):
    """
    :param snapshot_matrix: M x N matrix with N beeing the number of snapshots, M is the ODE dimension
    :param transforms: Transformations
    :param nmodes_max: maximal number of modes allowed in each frame, default is the number of snapshots N
                    Note: it is good to put a number here that is large enough to get the error down but smaller then N,
                    because it will increase the performance of the algorithm
    :param eps: stopping criteria
    :param Niter: maximal number of iterations
    :param visualize: if true: show intermediet results
    :return:
    """
    assert (np.ndim(snapshot_matrix) == 2), "Are you stephen hawking, trying to solve this problem in 16 dimensions?" \
                             "Please give me a snapshotmatrix with every snapshot in one column"
    if use_rSVD:
        warn("Using rSVD to accelarate decomposition procedure may lead to different results, pls check!")
    #########################
    ## 1.Step: Initialize
    #########################
    qtilde = np.zeros_like(snapshot_matrix)
    E = np.zeros_like(snapshot_matrix)
    Nframes = len(transforms)

    # make a list of the number of maximal ranks in each frame
    if not np.all(nmodes_max): # check if array is None, if so set nmodes_max onto N
        nmodes_max = np.max(np.shape(snapshot_matrix))
    if np.size(nmodes_max) != Nframes:
            nmodes = list([nmodes_max]) * Nframes
    else:
            nmodes = [nmodes_max]
    qtilde_frames = [frame(trafo, qtilde, number_of_modes=nmodes[k]) for k,trafo in enumerate(transforms)]

    q = snapshot_matrix.copy()
    #Y = q.copy()
    Y = np.zeros_like(snapshot_matrix)
    norm_q = norm(reshape(q, -1))
    it = 0
    M, N = np.shape(q)
    #mu = 0.5/norm(q,ord="fro")**2*100
    if mu is None:
        mu = N * M / (4 * np.sum(np.abs(q)))
    if lambd is None:
        lambd =  1 / np.sqrt(np.maximum(M, N))
    thresh = 1e-7 * norm_q
    mu_inv = 1 / mu
    rel_err = 1
    res_old = 0
    rel_err_list = []
    while rel_err > eps and it < Niter:
        it += 1  # counts the number of iterations in the loop
        #############################
        # 2.Step: set qtilde to 0
        #############################
        qtilde = np.zeros_like(q)
        ranks = []
        ###########################
        # 3. Step: update frames
        ##########################
        t = time.time()

        for k, (trafo, q_frame) in enumerate(zip(transforms, qtilde_frames)):
            qtemp = 0
            for p, (trafo_p, frame_p) in enumerate(zip(transforms, qtilde_frames)):
                if p != k:
                    qtemp += trafo_p.apply(frame_p.build_field())
            qk = trafo.reverse(q - qtemp - E + mu_inv * Y)
            #qk = trafo.reverse(q - qfield_list[k] - E + mu_inv * Y)
            [U, S, VT] = SVT(qk, mu_inv, q_frame.Nmodes, use_rSVD)
            rank = np.sum(S > 0)
            q_frame.modal_system = {"U": U[:,:rank], "sigma": S[:rank], "VT": VT[:rank,:]}
            ranks.append(rank) # list of ranks for each frame
            qtilde += trafo.apply(q_frame.build_field())
        ###########################
        # 4. Step: update noice term
        ##########################
        E = shrink(q - qtilde + mu_inv * Y, lambd * mu_inv)
        #############################
        # 5. Step: update multiplier
        #############################
        res = q - qtilde - E
        Y = Y + mu * res

        #############################
        # 6. Step: update mu
        #############################
        dres = norm(res,ord='fro') - res_old
        res_old =  norm(res,ord='fro')
        norm_dres = np.abs(dres)

        norm_res = norm(reshape(res, -1))
        rel_err = norm_res / norm_q
        rel_err_list.append(rel_err)
        elapsed = time.time() - t
        print("it=%d rel_err= %4.4e norm(dres) = %4.1e norm(E)/norm(q) = %4.1e tcpu = %2.2f, ranks_frame = " % (
        it, rel_err, mu*norm_dres/norm_q, norm(reshape(E, -1))/norm_q, elapsed), *ranks)


    qtilde = 0
    for p, (trafo_p, frame_p) in enumerate(zip(transforms, qtilde_frames)):
            qtilde += trafo_p.apply(frame_p.build_field())
            S =frame_p.modal_system["sigma"]
            frame_p.Nmodes = np.sum(S > 0)

    return ReturnValue(qtilde_frames, qtilde, rel_err_list, E, ranks)



def save_frames(fname, frames,  error_matrix= None):

    fname_base, old_ext = os.path.splitext(fname)
    ext = ".pkl"
    for k,frame in enumerate(frames):
        fname_frame = fname_base + "_%.2d"%k + ext
        print("frame %2d saved to: "%k, fname_frame)
        frame.save(fname_frame)
    if error_matrix is not None:
        fname_error_matrix = fname_base+"_error_mat.npy"
        np.save(fname_error_matrix,error_matrix)

def load_frames(fname, Nframes, load_ErrMat = False):
    fname_base, old_ext = os.path.splitext(fname)
    ext = ".pkl"

    # load frames
    frame_list = []
    for k in range(Nframes):
        fname_frame = fname_base + "_%.2d" % k + ext
        print("frame %2d loaded: " % k, fname_frame)
        newframe= frame(fname = fname_frame)
        frame_list.append(newframe)

    # load sparse error matrix
    fname_error_matrix = fname_base+"_error_mat.npy"
    if load_ErrMat and os.path.isfile(fname_error_matrix):
        E = np.load(fname_error_matrix)
        return frame_list, E
    else:
        return frame_list




