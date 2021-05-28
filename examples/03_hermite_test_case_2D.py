#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2D MOVING DISCS

Created on Sat Jan  2 14:52:26 2021

@author: phil
"""

###############################################################################
# IMPORTED MODULES
###############################################################################
import sys
sys.path.append('../lib')
import numpy as np
from numpy import exp, mod,meshgrid,pi,sin,size
import matplotlib.pyplot as plt
from sPOD_tools import frame, sPOD_distribute_residual, shifted_rPCA
from transforms import transforms
from plot_utils import show_animation
from scipy.special import eval_hermite
from farge_colormaps import farge_colormap_multi
###############################################################################
cm = farge_colormap_multi()
##########################################
#%% Define your DATA:
##########################################
plt.close("all")
Ngrid = [201, 202]  # number of grid points in x
Nt = 200            # Number of time intervalls
Nvar = 1            # Number of variables
nmodes = [10,5]          # reduction of singular values

data_shape = [*Ngrid,Nvar,Nt]
               # size of time intervall
T = 2*pi                # total time
L = np.asarray([30, 5])   # total domain size
x0 = L*0.5               # starting point of the gauss puls
R = 0.1 * min(L)         # Radius of cylinder
x,y = (np.linspace(-L[i]/2, L[i]/2, Ngrid[i]) for i in range(2))
time = np.linspace(0, T, Nt)
dx,dy = (x[1]-x[0],y[1]-y[0])
dt = time[1]-time[0]
c = dx/dt
[Y,X] = meshgrid(y,x)


f = lambda x,l : ((np.tanh(x/l) + 1 ) * 0.5)
# gauss hermite polynomials of order n
psi = lambda n,x: (2**n*np.math.factorial(n)*np.sqrt(np.pi))**(-0.5)*np.exp(-x**2/2)*eval_hermite(n,x)
#CoefList = [np.random.rand()) for n in range(20)];
#CoefList = [c/np.linalg.norm(c) for c in CoefList]
CoefList1 = np.exp(-0.1*np.arange(0,nmodes[0]))
CoefList2 = np.exp(-0.01*np.arange(0,nmodes[1]))
Dyadsum1 = lambda x,t : np.sum([c * psi(n, x)*np.cos((n+2)*t) for n,c in enumerate(CoefList1)],0)
Dyadsum2 = lambda x,t : np.sum([c * psi(n, x)*np.sin((n+2)*t) for n,c in enumerate(CoefList2)],0)
field1 = lambda x,y,t: Dyadsum1(x,t)*psi(0,4*y)
field2 = lambda x,y,t: Dyadsum2(x,t)*psi(0,4*y)

q = np.zeros(data_shape)
q1 = np.zeros(data_shape)
q2 = np.zeros(data_shape)
shift1, shift2, shift3 = [np.zeros([2,Nt])]*3

d = np.zeros([Ngrid[0],Nt])
center1 = (0.2*L[0],0.5*L[1])
center2 = (0.5*L[0],0.5*L[1])

for it,t in enumerate(time):
    
    x1,y1 = (center1[0],center1[1]+ 0.3*L[1]*sin(t))
    x2,y2 = (center2[0]-0.3*L[1]*sin(t), - 0.3*L[1]*sin(t) + center2[1])
    
    
    shift1[0,it] = x1-center1[0]
    shift1[1,it] = y1-center1[1]
    
    shift2[0,it] = x2-center2[0]
    shift2[1,it] = y2-center2[1]

    shift3[0,it] = 0
    shift3[1,it] = 0

    d[:, it] = Dyadsum1(x, t)
    q1[..., 0, it] = field1(X+5,Y,t)
    q2[..., 0, it] = field2(X, Y, t)
    #plt.pcolormesh(X,Y,q[...,0,it])
    #plt.show()
    #plt.pause(0.001)
    
    

# %% Create Trafo

shift_trafo_1 = transforms(data_shape,L, shifts = shift1, dx = [dx,dy] , use_scipy_transform=True)
shift_trafo_2 = transforms(data_shape,L, shifts = shift2, dx = [dx,dy] , use_scipy_transform=True)
shift_trafo_3 = transforms(data_shape,L, shifts = shift3, dx = [dx,dy], use_scipy_transform=False )

q = shift_trafo_1.reverse(q1) + shift_trafo_2.reverse(q2)



qshift1 = shift_trafo_1.apply(q)
qshift2 = shift_trafo_2.apply(q)
qshiftreverse = shift_trafo_2.reverse(shift_trafo_2.apply(q))
res = q-qshiftreverse
err = np.linalg.norm(np.reshape(res,-1))/np.linalg.norm(np.reshape(q,-1))
print("err =  %4.4e "% err)
plt.pcolormesh(X,Y,q[...,0,0]-qshiftreverse[...,0,0], cmap = cm)
plt.colorbar()
plt.show()
# %% Test Trafo

# figs,axs = plt.subplots(3,1,sharex=True)
# axs[0].pcolormesh(X,Y,qshift1[...,0,0])
# axs[1].pcolormesh(X,Y,qshift2[...,0,0])
# axs[2].pcolormesh(X,Y,q[...,0,0]-qshiftreverse[...,0,0])
# axs[0].set_title(r"$q^1$ Frame 1")
# axs[1].set_title(r"$q^2$ Frame 2")
# axs[2].set_title(r"$q - T^s_1 q^1 + T^s_2 q^2$ Data")
# for it in range(Nt):
#     axs[0].pcolormesh(X,Y,qshift1[...,0,it])
#     axs[1].pcolormesh(X,Y,qshift2[...,0,it])
#     axs[2].pcolormesh(X,Y,q[...,0,it]-qshiftreverse[...,0,it])
#     plt.show()
#     plt.pause(0.001)
    
# %% Run shifted POD
transforms = [shift_trafo_1, shift_trafo_2]
#qframes, qtilde = sPOD_distribute_residual(np.reshape(q,[-1,Nt]), transforms, nmodes=nmodes, eps=1e-4, Niter=50, visualize=True, use_rSVD=False)
qframes, qtilde = shifted_rPCA(np.reshape(q,[-1,Nt]), transforms, eps=1e-10, Niter=10, visualize=True)

U, S1, VT = np.linalg.svd(np.reshape(q1,[-1,Nt]),full_matrices=False)
U, S2, VT = np.linalg.svd(np.reshape(q2,[-1,Nt]),full_matrices=False)
S1f = qframes[0].modal_system["sigma"]
S2f = qframes[1].modal_system["sigma"]
plt.figure(3)
plt.semilogy(S1, '--*', label = r"exact $q^1$ ")
plt.semilogy(S2, '-o', label = r"exact $q^2$ ")
plt.semilogy(S1f, 'x', label = r"sPOD $q^1$")
plt.semilogy(S2f, '<', label = r"sPOD $q^2$")
plt.xlabel(r"rank $r_k$")
plt.ylabel(r"singular values $\sigma_r(q^k)$")
plt.xlim([-1,50])
plt.legend()